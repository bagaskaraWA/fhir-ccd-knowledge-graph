r"""
crs_eval.py
===========
Guideline-concordance evaluation for the CCD CRS (Bab IV, T2b).

Two modes:
  worksheet <pid>   Generate eval/worksheet_<pid>.csv -- every positive rec with
                    its text + condition hint + an empty `gold_applicable` column,
                    and print the patient's clinical picture so a human can label
                    each rec 1/0 by applying the guideline TEXT to the record.
                    (Universal recs -> almost always 1; condition-specific recs ->
                    1 only if the patient meets the precondition, incl. text-only
                    ones like "LVEF <=40%" the system can't see.)
  score             Read every filled eval/worksheet_*.csv (MANUAL gold), run the
                    system's gate+AND applicable query per patient, and report
                    Precision / Recall / F1 (macro + micro), plus FP-by-discrimination-
                    class and FN islanded-vs-reachable breakdowns.
  score-oracle      Same, but gold = eval/silver_oracle_labels.csv (the AUTOMATED
                    rule-based reference standard, silver_oracle.py; validated vs the
                    manual gold at Cohen's kappa=0.984). Fully-automated concordance.

Gold standard = human clinical judgment against the guideline text, INCLUDING
preconditions the flat KG cannot encode. So system false positives are the
false-baseline/vacuous over-inclusion, and false negatives split into
data-coverage (islanded) vs genuine misses -- both reported separately.

  safety            Generate eval/safety_worksheet.csv -- every contraindication
                    flag the UNARY system raises across the concordance cohort,
                    with the rec's population condition + whether the patient meets
                    it, for a human to label gold_true_contra 1/0.
  safety-score      Score UNARY (on-drug) vs POPULATION-GATED contraindication
                    detection against the gold labels (precision/recall + the
                    negation/conjunction/islanded false negatives).

Runs in .venv (dep: neo4j). Env vars as in crs_briefing.py (NEO4J_*).
Usage:
    .\.venv\Scripts\python.exe crs_eval.py worksheet <patientId>
    .\.venv\Scripts\python.exe crs_eval.py score
    .\.venv\Scripts\python.exe crs_eval.py safety
    .\.venv\Scripts\python.exe crs_eval.py safety-score
"""

import os
import sys
import csv
import glob

import obs_gate  # observation-gate registry (features + predicates + decide)
import nsaid_csv  # graph-native NSAID chronicity (gates the APT:10 safety flag)

NEO4J_URI      = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "sihdfhir")

GATE_CUI = "C0151744"
EVAL_DIR = "eval"
SNOMED = "http://snomed.info/sct"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"

# ── Cypher ───────────────────────────────────────────────────────────────────

# System's applicable set: gate on CCD, AND over bridgeable non-anchor conditions.
# FHIR-native: patient keyed on `uid`; conditions/procedures reach codes via
# SUBJECT + CODE; SAME_CONCEPT targets the shared :Code node.
Q_SYSTEM_APPLICABLE = """
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
RETURN rec.recommendationId AS recId
"""

# All positive recs + a condition hint (curated non-anchor condition names).
Q_ALL_POSITIVE = """
MATCH (rec:Recommendation)
WHERE NOT rec.cor STARTS WITH '3'
OPTIONAL MATCH (rec)-[:TARGETS]->(tc:Concept) WHERE tc.umlsCui <> $gate
WITH rec, collect(DISTINCT tc.umlsName) AS conditionHint
RETURN rec.recommendationId AS recId, rec.cor AS cor, rec.text AS text,
       conditionHint
ORDER BY recId
"""

# Discrimination class per positive rec (graph-wide), for the FP/FN breakdowns.
Q_REC_CLASS = """
MATCH (rec:Recommendation)
WHERE NOT rec.cor STARTS WITH '3'
OPTIONAL MATCH (rec)-[:TARGETS]->(allc:Concept) WHERE allc.umlsCui <> $gate
WITH rec, collect(DISTINCT allc) AS allExtra
WITH rec, allExtra,
     [c IN allExtra WHERE EXISTS { (c)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Condition) }
                       OR EXISTS { (c)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Procedure) }] AS bridgeable
RETURN rec.recommendationId AS recId,
       CASE
         WHEN size(allExtra)   = 0                  THEN 'BASELINE'
         WHEN size(bridgeable) = 0                  THEN 'VACUOUS'
         WHEN size(bridgeable) < size(allExtra)     THEN 'PARTIAL'
         ELSE                                            'DISCRIMINATING'
       END AS cls,
       size(allExtra) > 0 AND size(bridgeable) = 0 AS unreachable
"""

Q_PATIENT_CONDITIONS = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.system = '{SNOMED}'
RETURN DISTINCT k.display AS name ORDER BY name
"""
# medication[x] is a choice type: MEDICATION -> inline :Code OR :Medication (-> :CODE).
# Resolve mk either way so referenced prescriptions are not dropped.
Q_PATIENT_MEDS = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(x)
OPTIONAL MATCH (x)-[:CODE]->(xc:Code)
WITH CASE WHEN x:Code THEN x ELSE xc END AS mk
WHERE mk IS NOT NULL AND mk.system = '{RXNORM}'
RETURN DISTINCT mk.display AS name ORDER BY name
"""

# Safety flags: patient is ON a drug some rec CONTRAINDICATES (the UNARY system).
# Also report the rec's population condition (non-anchor TARGETS), whether it
# bridges, and whether THIS patient meets it -- so a population-GATED variant can
# be scored against the same gold labels. Resolves both med paths.
Q_SAFETY_FLAGS = """
MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(x)
OPTIONAL MATCH (x)-[:CODE]->(xc:Code)
WITH p, CASE WHEN x:Code THEN x ELSE xc END AS mk
WHERE mk IS NOT NULL
MATCH (mk)<-[:SAME_CONCEPT]-(:Concept)<-[:CONTRAINDICATES]-(rec:Recommendation)
OPTIONAL MATCH (rec)-[:TARGETS]->(tc:Concept) WHERE tc.umlsCui <> $gate
WITH p, mk, rec, collect(DISTINCT tc) AS popConds
RETURN rec.recommendationId AS recId, mk.display AS drug, rec.text AS text,
       [c IN popConds | c.umlsName] AS popCondNames,
       size([c IN popConds WHERE EXISTS { (c)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Condition) }]) AS popBridgeable,
       size([c IN popConds WHERE EXISTS {
             (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code)<-[:SAME_CONCEPT]-(c) }]) AS popMatched
ORDER BY recId
"""


def _connect():
    from neo4j import GraphDatabase
    if not NEO4J_PASSWORD:
        sys.exit("ERROR: set NEO4J_PASSWORD.")
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


_OBS_GATES = os.environ.get("OBS_GATES", "1") != "0"   # OBS_GATES=0 -> parity arm


def _rows(session, q, **p):
    rows = [r.data() for r in session.run(q, **p)]
    if not _OBS_GATES:
        return rows
    # Observation gating: re-decide obs-gated recs via obs_gate (composes AND/OR
    # correctly, incl. disjunctive RAAI:1's LVEF branch), and promote them to
    # DISCRIMINATING in the class table.
    if q is Q_SYSTEM_APPLICABLE:
        feats = obs_gate.features(session, p["pid"])
        final = obs_gate.decide({r["recId"] for r in rows}, feats)
        return [{"recId": r} for r in sorted(final)]
    if q is Q_REC_CLASS:
        for r in rows:
            if r["recId"] in obs_gate.OBS_GATED:
                r["cls"] = "DISCRIMINATING"
                r["unreachable"] = False
    return rows


# ── worksheet mode ─────────────────────────────────────────────────────────────

def make_worksheet(pid):
    os.makedirs(EVAL_DIR, exist_ok=True)
    drv = _connect()
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            conds = [r["name"] for r in _rows(s, Q_PATIENT_CONDITIONS, pid=pid)]
            meds  = [r["name"] for r in _rows(s, Q_PATIENT_MEDS, pid=pid)]
            recs  = _rows(s, Q_ALL_POSITIVE, pid=pid, gate=GATE_CUI)
    finally:
        drv.close()

    print("=" * 70)
    print(f"PATIENT {pid} -- clinical picture (label recs against THIS + guideline text)")
    print("=" * 70)
    print("CONDITIONS:")
    for c in conds:
        print(f"  - {c}")
    print("MEDICATIONS:")
    for m in meds:
        print(f"  - {m}")
    print("\nNOTE: also consider text-only preconditions (LVEF, LDL, 'on DAPT', "
          "'requires anticoagulation') -- check Synthea observations if needed.")

    path = os.path.join(EVAL_DIR, f"worksheet_{pid}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["recId", "cor", "gold_applicable", "conditionHint", "text"])
        for r in recs:
            hint = "; ".join([h for h in r["conditionHint"] if h]) or "(universal)"
            w.writerow([r["recId"], r["cor"], "", hint, r["text"]])
    print(f"\nWrote {path} ({len(recs)} recs). Fill `gold_applicable` with 1/0.")


# ── score mode ─────────────────────────────────────────────────────────────────

def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _load_gold_from_worksheets():
    """{pid: set(full recId)} from filled manual worksheets (gold_applicable == 1)."""
    gold = {}
    for path in sorted(glob.glob(os.path.join(EVAL_DIR, "worksheet_*.csv"))):
        pid = os.path.basename(path)[len("worksheet_"):-len(".csv")]
        s = set()
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("gold_applicable") or "").strip() == "1":
                    s.add(row["recId"])
        gold[pid] = s
    if not gold:
        sys.exit(f"No worksheets in {EVAL_DIR}/. Run 'worksheet <pid>' and fill them first.")
    return gold


def _load_gold_from_oracle(positive_full):
    """{pid: set(full recId)} from eval/silver_oracle_labels.csv, restricted to POSITIVE recs.
    Oracle recIds are short (APT:1); map to the graph's full form (CCD-2023:APT:1)."""
    path = os.path.join(EVAL_DIR, "silver_oracle_labels.csv")
    if not os.path.exists(path):
        sys.exit(f"{path} not found -- run 'silver_oracle.py label' first.")
    short2full = {rid.replace("CCD-2023:", ""): rid for rid in positive_full}
    gold = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = (row.get("patientId") or "").strip()
            gold.setdefault(pid, set())
            if (row.get("oracle_label") or "").strip() != "1":
                continue
            short = (row.get("recId") or "").replace("CCD-2023:", "").strip()
            if short in short2full:                    # positive recs only (excludes cor-3)
                gold[pid].add(short2full[short])
    return gold


def score(gold_source="worksheet"):
    drv = _connect()
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            cls_rows = _rows(s, Q_REC_CLASS, gate=GATE_CUI)
            rec_cls   = {r["recId"]: r["cls"] for r in cls_rows}
            rec_unrch = {r["recId"]: r["unreachable"] for r in cls_rows}

            gold_map = (_load_gold_from_oracle(set(rec_cls.keys()))
                        if gold_source == "oracle" else _load_gold_from_worksheets())

            tot_tp = tot_fp = tot_fn = 0
            macro = []
            fp_by_cls, fn_by_reach = {}, {"islanded": 0, "reachable_miss": 0}
            fp_by_rec, fn_by_rec = {}, {}

            for pid in sorted(gold_map):
                gold = gold_map[pid]
                system = {r["recId"] for r in _rows(s, Q_SYSTEM_APPLICABLE, pid=pid, gate=GATE_CUI)}

                tp = len(gold & system)
                fp = len(system - gold)
                fn = len(gold - system)
                p, r, f = _prf(tp, fp, fn)
                macro.append((p, r, f))
                tot_tp += tp; tot_fp += fp; tot_fn += fn

                for rid in (system - gold):
                    c = rec_cls.get(rid, "?")
                    fp_by_cls[c] = fp_by_cls.get(c, 0) + 1
                    fp_by_rec[rid] = fp_by_rec.get(rid, 0) + 1
                for rid in (gold - system):
                    fn_by_reach["islanded" if rec_unrch.get(rid) else "reachable_miss"] += 1
                    fn_by_rec[rid] = fn_by_rec.get(rid, 0) + 1

                print(f"  {pid}: P={p:.2f} R={r:.2f} F1={f:.2f}  (tp={tp} fp={fp} fn={fn})")
    finally:
        drv.close()

    n = len(macro)
    mp = sum(x[0] for x in macro) / n
    mr = sum(x[1] for x in macro) / n
    mf = sum(x[2] for x in macro) / n
    up, ur, uf = _prf(tot_tp, tot_fp, tot_fn)

    print("\n" + "=" * 70)
    print(f"GOLD SOURCE: {gold_source}    PATIENTS: {n}")
    print(f"MACRO  P={mp:.3f}  R={mr:.3f}  F1={mf:.3f}")
    print(f"MICRO  P={up:.3f}  R={ur:.3f}  F1={uf:.3f}   (tp={tot_tp} fp={tot_fp} fn={tot_fn})")
    print(f"\nFALSE POSITIVES by discrimination class (the over-inclusion): {fp_by_cls}")
    print(f"FALSE NEGATIVES by reachability: {fn_by_reach}")
    print("  -> recall against the BRIDGEABLE subset excludes the 'islanded' FNs.")

    # ── per-recommendation error tables (which recs drive each error type) ──
    def _short(rid): return rid.replace("CCD-2023:", "")

    print("\n" + "=" * 70)
    print("FALSE POSITIVES by recommendation (over-inclusion), most-frequent first:")
    print(f"  {'rec':<12} {'class':<15} {'FP':>4}")
    for rid, k in sorted(fp_by_rec.items(), key=lambda x: -x[1]):
        print(f"  {_short(rid):<12} {rec_cls.get(rid,'?'):<15} {k:>4}")
    genuine = [(rid, k) for rid, k in fp_by_rec.items() if rec_cls.get(rid) in ("DISCRIMINATING", "PARTIAL")]
    if genuine:
        print("\n  -- GENUINE over-fires (DISCRIMINATING/PARTIAL = the real precision errors) --")
        for rid, k in sorted(genuine, key=lambda x: -x[1]):
            print(f"     {_short(rid):<12} {rec_cls.get(rid):<15} {k:>4}")

    print("\n" + "=" * 70)
    print("FALSE NEGATIVES by recommendation (recall gap), most-frequent first:")
    print(f"  {'rec':<12} {'class':<15} {'reach':<10} {'FN':>4}")
    for rid, k in sorted(fn_by_rec.items(), key=lambda x: -x[1]):
        reach = "islanded" if rec_unrch.get(rid) else "reachable"
        print(f"  {_short(rid):<12} {rec_cls.get(rid,'?'):<15} {reach:<10} {k:>4}")


# ── safety-detection eval ───────────────────────────────────────────────────────
# Cohort = the same patients you built concordance worksheets for. We label every
# contraindication flag the UNARY system raises, then score two query variants:
#   UNARY  -- flag if the patient is on the contraindicated drug (current behavior).
#   GATED  -- flag only if the patient ALSO meets the rec's bridgeable population
#             condition. Higher precision, but misses negation-defined (BB:4) and
#             conjunctive (SHA:3) contraindications the schema can't gate.

def _worksheet_pids():
    pids = []
    for path in sorted(glob.glob(os.path.join(EVAL_DIR, "worksheet_*.csv"))):
        pids.append(os.path.basename(path)[len("worksheet_"):-len(".csv")])
    return pids


def make_safety_worksheet():
    pids = _worksheet_pids()
    if not pids:
        sys.exit(f"No concordance worksheets in {EVAL_DIR}/ -- run 'worksheet <pid>' "
                 f"first so the safety eval uses the same cohort.")
    os.makedirs(EVAL_DIR, exist_ok=True)
    drv = _connect()
    rows = []
    try:
        with drv.session(database=NEO4J_DATABASE) as s:
            for pid in pids:
                for r in _rows(s, Q_SAFETY_FLAGS, pid=pid, gate=GATE_CUI):
                    rows.append((pid, r["recId"], r["drug"],
                                 "; ".join([n for n in r["popCondNames"] if n]) or "(none: text/negation/conjunction)",
                                 r["popBridgeable"], r["popMatched"], r["text"]))
    finally:
        drv.close()

    path = os.path.join(EVAL_DIR, "safety_worksheet.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["patientId", "recId", "drug", "gold_true_contra",
                    "popConditionHint", "popBridgeable", "popMatched", "text"])
        for pid, recId, drug, hint, pb, pm, text in rows:
            w.writerow([pid, recId, drug, "", hint, pb, pm, text])
    print(f"Wrote {path} ({len(rows)} unary flags across {len(pids)} patients).")
    print("Fill `gold_true_contra` 1/0: is THIS patient genuinely contraindicated per")
    print("the guideline TEXT (on the drug AND meeting the harmful precondition)?")


def safety_score():
    path = os.path.join(EVAL_DIR, "safety_worksheet.csv")
    if not os.path.exists(path):
        sys.exit(f"{path} not found -- run 'safety' first and fill gold_true_contra.")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            g = (row.get("gold_true_contra") or "").strip()
            if g in ("0", "1"):
                rows.append((row.get("patientId", ""), row.get("recId", "").replace("CCD-2023:", ""),
                             g == "1", int(row.get("popMatched") or 0) > 0))

    # Graph-native chronicity for the APT:10 rows (>=3 courses OR active), cached per patient.
    drv = _connect(); chron = {}
    with drv.session(database=NEO4J_DATABASE) as s:
        for pid, rec, _gold, _pm in rows:
            if rec == "APT:10" and pid not in chron:
                chron[pid] = nsaid_csv.chronicity_graph(s, pid)["chronic"]
    drv.close()

    u_tp = u_fp = 0; g_tp = g_fp = g_fn = 0; c_tp = c_fp = c_fn = 0
    a_tp = a_fp = a_fn = 0   # APT:10 rows only, chronicity-gated
    for pid, rec, gold, pm in rows:
        u_tp += gold; u_fp += (not gold)                              # UNARY: flag every row
        if pm and gold: g_tp += 1                                     # POPULATION-GATED
        elif pm and not gold: g_fp += 1
        elif (not pm) and gold: g_fn += 1
        cflag = chron.get(pid, True) if rec == "APT:10" else True     # CHRONICITY-GATED (APT:10)
        if cflag and gold: c_tp += 1
        elif cflag and not gold: c_fp += 1
        elif (not cflag) and gold: c_fn += 1
        if rec == "APT:10":
            if cflag and gold: a_tp += 1
            elif cflag and not gold: a_fp += 1
            elif (not cflag) and gold: a_fn += 1

    up = u_tp / (u_tp + u_fp) if (u_tp + u_fp) else 0.0
    ur = 1.0 if u_tp else 0.0   # unary flags all on-drug -> no reachable true miss
    gp, grr, gf = _prf(g_tp, g_fp, g_fn)
    cp, crr, cf = _prf(c_tp, c_fp, c_fn)
    ap, arr, af = _prf(a_tp, a_fp, a_fn)

    print("=" * 70)
    print("SAFETY-DETECTION EVAL (contraindication flags)")
    print("=" * 70)
    print(f"UNARY (on-drug):            P={up:.3f}  R~={ur:.3f}   (tp={u_tp} fp={u_fp})")
    print(f"POPULATION-GATED:           P={gp:.3f}  R ={grr:.3f}  F1={gf:.3f}   (tp={g_tp} fp={g_fp} fn={g_fn})")
    print(f"+ APT:10 CHRONICITY-GATED:  P={cp:.3f}  R ={crr:.3f}  F1={cf:.3f}   (tp={c_tp} fp={c_fp} fn={c_fn})")
    print(f"    APT:10 rows only:       P={ap:.3f}  R ={arr:.3f}  F1={af:.3f}   (tp={a_tp} fp={a_fp} fn={a_fn})")
    print("\nReading: unary matching never misses a reachable contraindication (recall~1) "
          "but over-fires (low precision). POPULATION-GATED raises precision; its false "
          "negatives are the negation-defined (BB:4) / conjunctive (SHA:3) / islanded cases "
          "the flat schema cannot gate. CHRONICITY-GATED replaces the unary APT:10 flag with "
          "graph-native chronicity (>=3 courses OR an active prescription) so APT:10 fires "
          "only for genuinely chronic NSAID users; on this chronic-comorbidity sample it "
          "matches unary, but cohort-wide it suppresses the acute-only NSAID users unary flags.")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: crs_eval.py [worksheet <pid> | score | score-oracle | safety | safety-score]")
    mode = sys.argv[1]
    if mode == "worksheet":
        if len(sys.argv) < 3:
            sys.exit("Usage: crs_eval.py worksheet <pid>")
        make_worksheet(sys.argv[2])
    elif mode == "score":
        score("worksheet")
    elif mode == "score-oracle":
        score("oracle")
    elif mode == "safety":
        make_safety_worksheet()
    elif mode == "safety-score":
        safety_score()
    else:
        sys.exit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
