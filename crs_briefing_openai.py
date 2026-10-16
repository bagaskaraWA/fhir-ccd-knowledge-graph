r"""
crs_briefing_openai.py
======================
OpenAI variant of crs_briefing.py. IDENTICAL retrieval + grounding logic
(graph-grounded RAG, the KG is the retriever); only the LLM call differs.

Pipeline:  patientId
  [1] RETRIEVE  -- deterministic Cypher (NO LLM): patient snapshot, applicable
                   guideline recommendations (baseline-gate + AND over extra
                   conditions), contraindication safety flags, literature-PMI
                   drug support.
  [2] ASSEMBLE  -- pack the query results into a compact JSON facts payload,
                   each item carrying its provenance (recommendation id, COR, PMID).
  [3] GROUND    -- one OpenAI chat-completion that PHRASES the facts into a
                   clinician briefing. The model never touches Neo4j and never
                   sees the schema -- it only re-words the structured facts,
                   cites each one, and is forbidden from adding anything new.
  [4] OUTPUT    -- the raw facts JSON (so faithfulness is checkable) + the briefing.

See crs_briefing.py header for the honesty guarantees and the documented
query-layer limitations (they are identical here).

Runs in .venv (3.14).  Deps:  pip install neo4j openai
Usage:
    .\.venv\Scripts\python.exe crs_briefing_openai.py <patientId>
    .\.venv\Scripts\python.exe crs_briefing_openai.py <patientId> --no-llm   # retrieval only
"""

import os
import sys
import json

# ── CONFIG (everything sensitive is read from env vars; nothing secret in this file) ──
NEO4J_URI      = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")            # REQUIRED -- no default
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "sihdfhir")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")            # REQUIRED unless --no-llm
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")  # cheap; fine for phrasing facts
# Token budget for the reply. On a REASONING model this also covers hidden
# reasoning tokens, so it must be generous or the visible answer comes back
# empty. 4000 is safe for a short briefing on either model family.
OPENAI_MAX_TOKENS = int(os.environ.get("OPENAI_MAX_TOKENS", "8000"))
# Reasoning effort for reasoning models (gpt-5.x / o-series). "none" disables
# hidden reasoning so the whole token budget goes to the visible briefing -- the
# right choice for this phrasing task (the reasoning is already in the Cypher).
# Automatically dropped for non-reasoning models (gpt-4o / gpt-4.1) that reject
# it. Set OPENAI_REASONING_EFFORT="" to omit the parameter entirely.
OPENAI_REASONING_EFFORT = os.environ.get("OPENAI_REASONING_EFFORT", "none")

GATE_CUI = "C0151744"   # Myocardial Ischemia -- the CCD cohort gate (NOT a discriminator)
PMI_ARTICLE_FLOOR = 3   # kill rare-meets-rare PMI singletons
SNOMED = "http://snomed.info/sct"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"

import obs_gate  # observation-gate registry (applied to the `applicable` facts)
import nsaid_csv  # graph-native NSAID chronicity (gates the APT:10 safety flag)

# ── Cypher (FHIR-native; $pid = patient uid, $gate = GATE_CUI) ───────────────────────
# Patient keyed on uid; conditions/procedures reach codes via SUBJECT + CODE;
# SAME_CONCEPT targets the shared :Code node; medication[x] resolves both the
# inline :Code and the :Medication-reference path.

Q_CONDITIONS = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.system = '{SNOMED}'
RETURN DISTINCT k.code AS code, k.display AS name
ORDER BY name
"""

Q_MEDICATIONS = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(x)
OPTIONAL MATCH (x)-[:CODE]->(xc:Code)
WITH CASE WHEN x:Code THEN x ELSE xc END AS mk
WHERE mk IS NOT NULL AND mk.system = '{RXNORM}'
RETURN DISTINCT mk.code AS code, mk.display AS name
ORDER BY name
"""

# Applicable POSITIVE recommendations: gate on CCD membership, then require ALL of
# the rec's bridgeable non-anchor condition targets (AND). Contraindications (cor 3)
# are handled by the dedicated safety query, so they're excluded here.
Q_APPLICABLE = """
MATCH (p:Patient {uid:$pid})
WHERE EXISTS { (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code)<-[:SAME_CONCEPT]-(:Concept {umlsCui:$gate}) }
MATCH (rec:Recommendation)
WHERE NOT rec.cor STARTS WITH '3'
OPTIONAL MATCH (rec)-[:TARGETS]->(tc:Concept)
  WHERE tc.umlsCui <> $gate
    AND ( EXISTS { (tc)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Condition) }
       OR EXISTS { (tc)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Procedure) } )
WITH p, rec, collect(DISTINCT tc) AS extraConds
WITH p, rec, extraConds,
     [tc IN extraConds WHERE
        EXISTS { (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code)<-[:SAME_CONCEPT]-(tc) }
        OR EXISTS { (p)<-[:SUBJECT]-(:Procedure)-[:CODE]->(:Code)<-[:SAME_CONCEPT]-(tc) }] AS matched
WHERE size(extraConds) = 0
   OR (coalesce(rec.targetLogic, 'AND') = 'OR'  AND size(matched) >= 1)
   OR (coalesce(rec.targetLogic, 'AND') = 'AND' AND size(matched) = size(extraConds))
OPTIONAL MATCH (rec)-[:RECOMMENDS]->(rc:Concept)
OPTIONAL MATCH (rec)-[:CITES]->(a:Abstract)
RETURN rec.recommendationId               AS recId,
       rec.cor                            AS cor,
       rec.sectionTitle                  AS section,
       rec.interventionType              AS interventionType,
       rec.text                          AS text,
       [c IN extraConds | c.umlsName]    AS requiresAlso,
       size(extraConds)                  AS extraCount,
       collect(DISTINCT rc.umlsName)     AS recommends,
       collect(DISTINCT a.pmid)          AS citedPmids
ORDER BY extraCount DESC, cor
"""

# Fetch one rec's briefing metadata -- to build a facts row for an obs-gated rec that
# the graph gate+AND did not return (the disjunctive RAAI LVEF-only branch).
Q_REC_META = """
MATCH (rec:Recommendation {recommendationId:$rid})
OPTIONAL MATCH (rec)-[:TARGETS]->(tc:Concept) WHERE tc.umlsCui <> $gate
WITH rec, collect(DISTINCT tc) AS extra
OPTIONAL MATCH (rec)-[:RECOMMENDS]->(rc:Concept)
WITH rec, extra, collect(DISTINCT rc.umlsName) AS recommends
OPTIONAL MATCH (rec)-[:CITES]->(a:Abstract)
RETURN rec.recommendationId AS recId, rec.cor AS cor, rec.sectionTitle AS section,
       rec.interventionType AS interventionType, rec.text AS text,
       [c IN extra | c.umlsName] AS requiresAlso, size(extra) AS extraCount,
       recommends AS recommends, collect(DISTINCT a.pmid) AS citedPmids
"""

# Contraindication safety: the patient is ALREADY ON a drug some rec contraindicates.
# (Simple unary match -- population-conditional refinement is a documented limitation.)
Q_SAFETY = """
MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(x)
OPTIONAL MATCH (x)-[:CODE]->(xc:Code)
WITH CASE WHEN x:Code THEN x ELSE xc END AS mk
WHERE mk IS NOT NULL
MATCH (mk)<-[:SAME_CONCEPT]-(:Concept)<-[:CONTRAINDICATES]-(rec:Recommendation)
RETURN DISTINCT mk.display AS drug, mk.code AS code,
       rec.recommendationId AS recId, rec.cor AS cor, rec.text AS text
ORDER BY drug
"""

# Literature support: drugs the corpus links to this patient's conditions, ranked by PMI.
# CO_OCCURS_IN_LITERATURE is materialized between :Code nodes.
Q_LITERATURE = """
MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(:Condition)-[:CODE]->(ck:Code)
MATCH (mk:Code)-[r:CO_OCCURS_IN_LITERATURE]->(ck)
WHERE r.articleCount >= $floor
RETURN ck.display AS condition, mk.display AS drug,
       round(r.pmi, 3) AS pmi, r.articleCount AS articleCount
ORDER BY r.pmi DESC
LIMIT 15
"""


# ── RETRIEVE ─────────────────────────────────────────────────────────────────────────

def _run(session, query, **params):
    rows = [record.data() for record in session.run(query, **params)]
    # Observation gating on the applicable set: re-decide obs-gated recs via obs_gate,
    # fetching metadata for any disjunctive additions the graph gate+AND didn't return.
    if query is Q_APPLICABLE:
        feats = obs_gate.features(session, params["pid"])
        graph_set = {r["recId"] for r in rows}
        final = obs_gate.decide(graph_set, feats)
        rows = [r for r in rows if r["recId"] in final]
        for rid in sorted(final - graph_set):
            rows.extend(r.data() for r in session.run(Q_REC_META, rid=rid, gate=GATE_CUI))
    return rows


def retrieve(pid):
    from neo4j import GraphDatabase
    if not NEO4J_PASSWORD:
        sys.exit("ERROR: set NEO4J_PASSWORD (see header). Aborting.")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            safety = _run(s, Q_SAFETY, pid=pid)
            # APT:10 (chronic-NSAID contraindication) is only appropriate for a genuinely
            # chronic NSAID user, so gate it on graph-native chronicity (>=3 courses OR an
            # active prescription); drop it for acute-only NSAID users.
            if not nsaid_csv.chronicity_graph(s, pid)["chronic"]:
                safety = [f for f in safety if not f.get("recId", "").endswith("APT:10")]
            facts = {
                "patientId":     pid,
                "conditions":    _run(s, Q_CONDITIONS,  pid=pid),
                "medications":   _run(s, Q_MEDICATIONS, pid=pid),
                "applicable":    _run(s, Q_APPLICABLE,  pid=pid, gate=GATE_CUI),
                "safetyFlags":   safety,
                "literature":    _run(s, Q_LITERATURE,  pid=pid, floor=PMI_ARTICLE_FLOOR),
            }
    finally:
        driver.close()
    return facts


# ── GROUND (LLM only phrases the facts) ──────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are summarizing decision-support facts retrieved from a clinical knowledge "
    "graph for a physician treating a patient with chronic coronary disease (CCD). "
    "The briefing INFORMS the clinician; it does not make the decision."
)

USER_TEMPLATE = """\
Write a clinician-facing briefing from the JSON facts below, in TWO clearly-headed
parts: a MAIN BRIEFING a cardiologist reads in 30 seconds, then a DETAILS chapter for
drill-down.

CONTENT RULES (strict -- these preserve trust):
- Use ONLY the facts provided. Never add recommendations, drugs, doses, or evidence
  that are not present in the JSON.
- Justify applicability ONLY from `requiresAlso` and the patient's actual `conditions` /
  `medications`. A rec's OTHER text preconditions are NOT established facts about this
  patient: never write "on oral anticoagulant", "post-PCI on anticoagulant", or
  "requires anticoagulation" unless an anticoagulant actually appears in `medications`.
  If a rec's action assumes such an unconfirmed precondition -- APT:11-16 assume the
  patient needs oral anticoagulation, yet the retrieval fires them on PCI history alone
  -- phrase the action CONDITIONALLY ("if on/requiring oral anticoagulation: ..."),
  never as an assertion. Cite only the `requiresAlso` condition as the trigger.
- Every item in `applicable` and `safetyFlags` MUST appear at least once, named by its
  recommendation id. You may GROUP and COMPRESS them, but never drop one.
- Never alter a COR value, and never attach a PMID to the wrong recommendation.
- State a count only if it equals the number of items given (say "N safety flags" only
  if `safetyFlags` has exactly N). Prefer naming items to counting them.
- If a list is empty, say so explicitly -- do not fill the gap.

=== PART 1 -- MAIN BRIEFING (must be readable in <= 30 seconds) ===
Tight and actionable. NO PMIDs, NO rationale prose, NO standard-care list in this part.
1. BOTTOM LINE -- 2-3 sentences: who this patient is (from `conditions`) and the single
   most important action plus the key safety concern.
2. SAFETY FLAGS (stop-and-check) -- one line each: drug -- concern [recId, COR].
3. ACTIONS FOR THIS PATIENT -- the `applicable` items with extraCount > 0 AND COR 1 or
   2a only (the stronger recommendations), as a terse list of the recommended option(s)
   [recId, COR], ordered COR 1 then 2a. WHAT to do only; the WHY, and the weaker COR 2b
   options, belong in Part 2.

=== PART 2 -- DETAILS & RATIONALE (drill-down) ===
1. FURTHER PATIENT-SPECIFIC OPTIONS (COR 2b) -- the remaining `applicable` items with
   extraCount > 0 and COR 2b ("may be considered"): one line each, the option(s)
   [recId, COR].
2. WHY THESE APPLY -- for EVERY patient-specific rec (Parts 1 and 2, all COR levels),
   one line naming the `requiresAlso` condition that triggered it.
3. STANDARD CCD CARE (applies to all CCD patients) -- the `applicable` items with
   extraCount = 0. COMPRESS: group by `section`, several per line, each tagged
   [recId, COR]. Do NOT give these one bullet each.
4. LITERATURE-SUPPORTED OPTIONS -- the `literature` entries in the order given
   (pmi, articleCount).
5. EVIDENCE -- a compact reference list mapping each recId to its citedPmids.

STYLE:
- Where a recommendation maps to many drug options, name the class and up to 3 examples,
  then "(+N more)" -- the full list is in the JSON and need not be inline.
- Short lines over paragraphs. No preamble, no closing disclaimer.
- Plain ASCII only (no emoji or symbols beyond standard punctuation).
- Head the two parts distinctly ("# MAIN BRIEFING" and "# DETAILS & RATIONALE") so they
  can be split apart.

FACTS:
{facts_json}
"""


def _chat(client, messages, max_out=1500, temperature=0):
    """chat.completions.create that adapts to newer model-family parameter rules.

    Older models (gpt-4o / gpt-4.1) take `max_tokens` + a free `temperature` and
    reject `reasoning_effort`. Newer families (gpt-5.x / o-series) instead:
      - reject `max_tokens` and require `max_completion_tokens`;
      - accept `reasoning_effort` ("none" disables hidden reasoning);
      - sometimes reject a non-default `temperature` (only 1 is allowed).
    We try the configured params, and on a parameter complaint we swap/drop the
    offending one and retry -- so the same script works across model families.
    """
    import openai
    params = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": max_out,
        "temperature": temperature,
    }
    if OPENAI_REASONING_EFFORT:
        params["reasoning_effort"] = OPENAI_REASONING_EFFORT
    for _ in range(5):
        try:
            return client.chat.completions.create(**params)
        except openai.BadRequestError as e:
            msg = str(e).lower()
            if "max_completion_tokens" in msg and "max_tokens" in params:
                params["max_completion_tokens"] = params.pop("max_tokens")
            elif "reasoning_effort" in msg and "reasoning_effort" in params:
                params.pop("reasoning_effort")     # non-reasoning model -> drop it
            elif "temperature" in msg and "temperature" in params:
                params.pop("temperature")          # model only allows its default
            else:
                raise                              # a real error, not a param-name mismatch
    raise RuntimeError("OpenAI rejected the request parameters after 5 adaptation attempts.")


def generate_briefing(facts):
    from openai import OpenAI
    if not OPENAI_API_KEY:
        sys.exit("ERROR: set OPENAI_API_KEY (or pass --no-llm). Aborting.")
    client = OpenAI(max_retries=8)  # reads OPENAI_API_KEY from env; auto-retries 429/5xx
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": USER_TEMPLATE.format(
            facts_json=json.dumps(facts, indent=2, default=str))},
    ]
    budget = OPENAI_MAX_TOKENS
    for attempt in range(2):
        resp = _chat(client, messages=messages, max_out=budget)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        if text:
            return text
        # Empty visible output: a reasoning model likely consumed the whole
        # budget on hidden reasoning (finish_reason == 'length'). Retry once
        # with a much larger budget before giving up.
        finish = getattr(choice, "finish_reason", None)
        if finish == "length" and attempt == 0:
            budget *= 4
            continue
        return (f"[no visible text returned; finish_reason={finish}. A reasoning "
                f"model likely spent the token budget on hidden reasoning -- raise "
                f"OPENAI_MAX_TOKENS (now {budget}) or use a non-reasoning model "
                f"like gpt-4.1 / gpt-4o, which is the right tool for this phrasing task.]")
    return "[empty output after retry -- raise OPENAI_MAX_TOKENS or switch models.]"


# ── MAIN ─────────────────────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:]]
    no_llm = "--no-llm" in args
    save = "--save" in args   # write facts JSON + briefing to eval/ as TWO separate UTF-8 files
    args = [a for a in args if a not in ("--no-llm", "--save")]
    if not args:
        sys.exit("Usage: python crs_briefing_openai.py <patientId> [--no-llm] [--save]")
    pid = args[0]

    facts = retrieve(pid)
    counts = {k: len(v) for k, v in facts.items() if isinstance(v, list)}
    facts_path = f"eval/briefing_facts_{pid}.json"
    brief_path = f"eval/briefing_{pid}.md"

    # --save writes two clean files (no stdout redirect needed, so no UTF-16 surprises);
    # without --save, everything goes to stdout as before.
    if save:
        os.makedirs("eval", exist_ok=True)
        with open(facts_path, "w", encoding="utf-8") as f:
            json.dump(facts, f, indent=2, default=str)
        print(f"-- facts {counts} -> {facts_path}")
    else:
        print("=" * 70)
        print(f"RETRIEVED FACTS for patient {pid}")
        print("=" * 70)
        print(json.dumps(facts, indent=2, default=str))
        print(f"\n-- counts: {counts}")

    if no_llm:
        if not save:
            print("\n-- --no-llm set: skipping the LLM briefing. --")
        return

    briefing = generate_briefing(facts)
    if save:
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(briefing)
        print(f"-- briefing -> {brief_path}")
    else:
        print("\n" + "=" * 70)
        print("GROUNDED BRIEFING")
        print("=" * 70)
        print(briefing)


if __name__ == "__main__":
    main()
