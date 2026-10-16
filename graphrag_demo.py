r"""
graphrag_demo.py -- a playground for GraphRAG over the sihdfhir graph.

NOT part of the thesis. This is deliberately more open-ended than crs_briefing.py:
that one answers a fixed question (what applies to patient X?) with fixed Cypher.
This one takes an arbitrary natural-language question and *discovers* what to
retrieve by walking the graph.

Pipeline
    question
      -> 1. ANCHOR   fuzzy-match question terms against the 1,395 :Code display names
      -> 2. BRIDGE   :Code -> :Concept via SAME_CONCEPT
      -> 3. EXPAND   concepts -> guideline recommendations (TARGETS/RECOMMENDS/
                     CONTRAINDICATES), codes -> co-occurring drugs by PMI,
                     recommendations -> cited abstracts
      -> 4. GROUND   cohort counts for the anchors, straight from the patient data
      -> 5. RENDER   a compact context block, printed so you can see exactly what
                     an LLM would be given
      -> 6. (--llm)  optionally hand that block to Claude to phrase an answer

The retrieval half needs no API key and is the interesting part -- run it bare to
watch the subgraph come back. --llm only adds the phrasing step.

Usage
    python graphrag_demo.py "what drugs are linked to diabetic kidney disease?"
    python graphrag_demo.py "prior MI and CKD -- what does the guideline say?" -v
    python graphrag_demo.py "is ibuprofen a problem in coronary disease?" --llm

Env: NEO4J_PASSWORD (default fhirneo4j), NEO4J_DATABASE (default sihdfhir),
     ANTHROPIC_API_KEY only when --llm is used.
"""
import argparse
import math
import os
import re
import sys
import textwrap

from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "fhirneo4j")
DATABASE = os.environ.get("NEO4J_DATABASE", "sihdfhir")

STOP = {
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "does",
    "do", "did", "is", "are", "was", "were", "be", "been", "being", "the", "a", "an",
    "and", "or", "but", "if", "then", "than", "with", "without", "for", "from", "to",
    "of", "in", "on", "at", "by", "as", "that", "this", "these", "those", "it", "its",
    "should", "would", "could", "can", "may", "might", "must", "have", "has", "had",
    "patient", "patients", "say", "says", "said", "about", "any", "all", "some",
    "problem", "linked", "link", "guideline", "guidelines", "there", "their",
}
MIN_TERM = 4


# ── 1. anchor ───────────────────────────────────────────────────────────────────
def terms(question):
    words = re.findall(r"[a-z0-9]+", question.lower())
    keep = [w for w in words if len(w) >= MIN_TERM and w not in STOP]
    # bigrams first: they are far more specific than single words
    grams = [f"{a} {b}" for a, b in zip(keep, keep[1:])] + keep
    return grams


def anchor(session, question, limit=8, verbose=False):
    """Match question terms against every :Code display name (only ~1.4k of them).

    Scoring is TF-IDF-ish and the IDF part matters more than it looks. Without it a
    generic word like "disease" matches hundreds of displays and drags in
    "Gingival disease" and "Leukemia" ahead of the term the question was actually
    about; weighting each term by how rare it is across the code vocabulary crushes
    those and promotes the specific ones.
    """
    codes = session.run(
        "MATCH (c:Code) WHERE c.display IS NOT NULL "
        "RETURN c.system AS system, c.code AS code, c.display AS display"
    ).data()
    lowered = [(c, c["display"].lower()) for c in codes]
    n_codes = len(lowered)
    grams = terms(question)

    scored, diag = {}, []
    for g in grams:
        hits = [(c, d) for c, d in lowered if g in d]
        if not hits:
            diag.append((g, 0, 0.0, "no match"))
            continue
        if len(hits) > n_codes * 0.25:                  # matches a quarter of the
            diag.append((g, len(hits), 0.0, "too common"))   # vocabulary: uninformative
            continue
        idf = math.log(n_codes / len(hits))
        bonus = 2.0 if " " in g else 1.0
        diag.append((g, len(hits), idf, ""))
        for c, d in hits:
            s = bonus * idf * (len(g) / max(len(d), 1)) * 100
            key = (c["system"], c["code"])
            if s > scored.get(key, (0, None))[0]:
                scored[key] = (s, c)

    if verbose:
        for g, h, idf, why in diag:
            note = f"  (dropped: {why})" if why else ""
            print(f"  [term] {g!r:<26} {h:>4} codes  idf={idf:.2f}{note}",
                  file=sys.stderr)
    out = [c for _, (s, c) in sorted(scored.items(), key=lambda kv: -kv[1][0])]
    return out[:limit], grams


# ── 2-4. bridge, expand, ground ─────────────────────────────────────────────────
Q_CONCEPTS = """
MATCH (c:Code {system:$system, code:$code})<-[:SAME_CONCEPT]-(k:Concept)
RETURN k.umlsCui AS cui
"""

# Everything below is keyed on the CONCEPT, not the code. Without this, the five
# strength variants of ibuprofen each retrieve the same recommendation and the same
# literature, and five near-identical blocks crowd the context window. The concept
# bridge already knows they are one thing -- so retrieve at that level and let the
# member codes be a detail.
Q_RECS = """
MATCH (r:Recommendation)-[rel]->(:Concept {umlsCui:$cui})
WHERE type(rel) IN ['TARGETS','RECOMMENDS','CONTRAINDICATES']
RETURN DISTINCT r.recommendationId AS recId, r.cor AS cor, r.loe AS loe,
       type(rel) AS edge, r.sectionTitle AS section, r.text AS text
ORDER BY recId
LIMIT 12
"""

Q_LITERATURE = """
MATCH (:Concept {umlsCui:$cui})-[:SAME_CONCEPT]->(:Code)
      -[r:CO_OCCURS_IN_LITERATURE]->(o:Code)
WHERE r.articleCount >= $floor
WITH o, max(r.pmi) AS pmi, max(r.articleCount) AS articles
RETURN o.display AS other, o.system AS system,
       round(pmi, 3) AS pmi, articles
ORDER BY pmi DESC
LIMIT 8
"""

Q_PMIDS = """
MATCH (r:Recommendation {recommendationId:$recId})-[:CITES]->(a:Abstract)
RETURN collect(DISTINCT a.pmid)[..8] AS pmids
"""

Q_COHORT = """
MATCH (:Concept {umlsCui:$cui})-[:SAME_CONCEPT]->(c:Code)
MATCH (p:Patient)<-[:SUBJECT]-()-[:CODE|MEDICATION]->(c)
RETURN count(DISTINCT p) AS n
"""

# Fallback for anchors whose code never bridged to a concept.
Q_COHORT_CODE = """
MATCH (p:Patient)<-[:SUBJECT]-()-[:CODE|MEDICATION]->(:Code {system:$system, code:$code})
RETURN count(DISTINCT p) AS n
"""


def retrieve(session, question, floor=3, verbose=False):
    anchors, grams = anchor(session, question, limit=20, verbose=verbose)
    if verbose:
        print(f"  [terms] {', '.join(grams[:12])}", file=sys.stderr)

    # Collapse anchors onto concepts; the first (best-scoring) display wins the label.
    groups, unbridged = {}, []
    for a in anchors:
        cuis = [r["cui"] for r in session.run(
            Q_CONCEPTS, system=a["system"], code=a["code"])]
        if not cuis:
            unbridged.append(a)
            continue
        cui = cuis[0]
        g = groups.setdefault(cui, {"label": a["display"], "members": []})
        g["members"].append(a)
    if verbose:
        print(f"  [anchors] {len(anchors)} codes -> {len(groups)} concepts "
              f"({len(unbridged)} unbridged)", file=sys.stderr)

    facts = []
    for cui, g in list(groups.items())[:6]:
        recs = session.run(Q_RECS, cui=cui).data()
        for r in recs:
            row = session.run(Q_PMIDS, recId=r["recId"]).single()
            r["pmids"] = row["pmids"] if row else []
        lit = session.run(Q_LITERATURE, cui=cui, floor=floor).data()
        n = session.run(Q_COHORT, cui=cui).single()
        facts.append({
            "label": g["label"], "cui": cui, "members": g["members"],
            "recs": recs, "literature": lit, "patients": n["n"] if n else 0,
        })
    for a in unbridged[:2]:
        n = session.run(Q_COHORT_CODE, system=a["system"], code=a["code"]).single()
        facts.append({
            "label": a["display"], "cui": None, "members": [a],
            "recs": [], "literature": [], "patients": n["n"] if n else 0,
        })
    return facts


# ── 5. render ───────────────────────────────────────────────────────────────────
def short_system(uri):
    for k, v in (("snomed", "SNOMED"), ("rxnorm", "RxNorm"), ("loinc", "LOINC")):
        if k in (uri or "").lower():
            return v
    return (uri or "?").rsplit("/", 1)[-1][:12]


def render(facts, width=94):
    L = []
    for f in facts:
        head = f"## {f['label']}"
        if f["cui"]:
            head += f"  [concept {f['cui']}]"
        L.append(head)
        mem = f["members"]
        if len(mem) == 1:
            L.append(f"   code: {short_system(mem[0]['system'])} {mem[0]['code']}")
        else:
            codes = ", ".join(f"{short_system(m['system'])} {m['code']}" for m in mem[:6])
            L.append(f"   {len(mem)} codes collapsed onto this concept: {codes}"
                     + (" ..." if len(mem) > 6 else ""))
        L.append(f"   patients in cohort: {f['patients']}")
        if f["recs"]:
            L.append("   guideline recommendations:")
            for r in f["recs"]:
                cite = f"  PMIDs {', '.join(map(str, r['pmids']))}" if r["pmids"] else ""
                L.append(f"     - [{r['recId']}] COR {r['cor']}, LOE {r['loe']}"
                         f" ({r['edge']}){cite}")
                for ln in textwrap.wrap(r["text"] or "", width - 9):
                    L.append(f"         {ln}")
        if f["literature"]:
            L.append("   literature co-occurrence (PMI-ranked):")
            for l in f["literature"]:
                L.append(f"     - {l['other']}  [{short_system(l['system'])}]"
                         f"  PMI {l['pmi']}, {l['articles']} articles")
        L.append("")
    return "\n".join(L)


# ── 6. optional phrasing ────────────────────────────────────────────────────────
SYSTEM = (
    "You answer clinical questions using ONLY the retrieved graph facts supplied. "
    "Every claim must trace to a fact. Cite recommendation ids in [brackets] and PMIDs "
    "where given. If the facts do not answer the question, say exactly what is missing "
    "rather than filling the gap from memory. Be brief."
)


def phrase(question, context, model="claude-sonnet-5"):
    try:
        import anthropic
    except ImportError:
        sys.exit("--llm needs the `anthropic` package (pip install anthropic)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("--llm needs ANTHROPIC_API_KEY in the environment")
    client = anthropic.Anthropic(max_retries=6)
    msg = client.messages.create(
        model=model, max_tokens=1200, system=SYSTEM,
        messages=[{"role": "user",
                   "content": f"QUESTION\n{question}\n\nRETRIEVED GRAPH FACTS\n{context}"}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", help="a natural-language question")
    ap.add_argument("--llm", action="store_true", help="also phrase an answer (needs a key)")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--floor", type=int, default=3, help="min articles for a PMI edge")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session(database=DATABASE) as s:
        facts = retrieve(s, a.question, floor=a.floor, verbose=a.verbose)
    driver.close()

    if not facts:
        print("No anchors matched. Try clinical wording closer to the coded terms, "
              "e.g. 'ischemic heart disease' rather than 'heart problems'.")
        return

    ctx = render(facts)
    nrec = sum(len(f["recs"]) for f in facts)
    nlit = sum(len(f["literature"]) for f in facts)
    print("=" * 94)
    print(f"RETRIEVED SUBGRAPH  --  {len(facts)} anchors, {nrec} recommendations, "
          f"{nlit} literature edges")
    print("=" * 94)
    print(ctx)

    if a.llm:
        print("=" * 94)
        print("GROUNDED ANSWER")
        print("=" * 94)
        print(phrase(a.question, ctx, a.model))


if __name__ == "__main__":
    main()
