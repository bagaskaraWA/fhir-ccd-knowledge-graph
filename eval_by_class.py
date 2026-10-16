r"""
eval_by_class.py -- guideline concordance split by how a recommendation discriminates.

The headline concordance figure blends populations that behave differently by
construction. A recommendation can discriminate between cohort members in two
independent ways, so the classification is 2x2 rather than binary:

                        | no observation gate | observation-gated
    ------------------- | ------------------- | ------------------
    no bridgeable target|  UNIVERSAL          |  VALUE-GATED
    has bridgeable      |  CONCEPT-MATCHED    |  BOTH
      condition target  |                     |

  UNIVERSAL        no discriminating mechanism at all: once a patient is in the
                   cohort the recommendation applies. Cannot over-fire for a cohort
                   member, and cannot discriminate either.
  CONCEPT-MATCHED  discriminates by graph traversal -- the patient must also carry a
                   code bridging to a further target concept.
  VALUE-GATED      discriminates only by a numeric predicate over an observation
                   (e.g. LVEF <= 40%), which no graph pattern can express.
  BOTH             discriminates by traversal and by predicate.

Splitting this way also localises the observation-gate ablation: only VALUE-GATED and
BOTH change between the two ablation arms, so any F1 difference must originate there.

Reuses crs_eval's queries and gold loader, so figures are directly comparable to the
headline numbers.

Usage
    NEO4J_PASSWORD=... python eval_by_class.py                  # gated arm
    NEO4J_PASSWORD=... OBS_GATES=0 python eval_by_class.py      # ablation baseline
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import crs_eval as E   # noqa: E402  -- reuse the evaluation machinery verbatim
import obs_gate        # noqa: E402  -- the set of observation-gated recommendations

# Mirrors the OPTIONAL MATCH in E.Q_SYSTEM_APPLICABLE exactly: a target counts only if
# it is not the gate concept and it actually bridges to a Condition or Procedure code.
Q_TARGETS = """
MATCH (r:Recommendation) WHERE NOT r.cor STARTS WITH '3'
OPTIONAL MATCH (r)-[:TARGETS]->(t:Concept)
  WHERE t.umlsCui <> $gate
    AND ( EXISTS { (t)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Condition) }
       OR EXISTS { (t)-[:SAME_CONCEPT]->(:Code)<-[:CODE]-(:Procedure) } )
WITH r, count(DISTINCT t) AS nt
RETURN r.recommendationId AS recId, nt
"""

ORDER = ["universal", "concept-matched", "value-gated", "both", "ALL"]


def classify(session):
    gated = set(obs_gate.OBS_GATED)
    cls = {}
    for r in E._rows(session, Q_TARGETS, gate=E.GATE_CUI):
        rid, has_target = r["recId"], r["nt"] > 0
        is_gated = rid in gated
        if has_target and is_gated:
            cls[rid] = "both"
        elif has_target:
            cls[rid] = "concept-matched"
        elif is_gated:
            cls[rid] = "value-gated"
        else:
            cls[rid] = "universal"
    return cls


def main():
    arm = "baseline (no observation gates)" if os.environ.get("OBS_GATES") == "0" \
        else "with observation gates"
    drv = E._connect()
    try:
        with drv.session(database=E.NEO4J_DATABASE) as s:
            cls = classify(s)
            groups = {name: {k for k, v in cls.items() if v == name}
                      for name in ORDER[:-1]}
            groups["ALL"] = set(cls)
            print(f"arm: {arm}")
            for name in ORDER:
                print(f"  {name:<16} {len(groups[name]):>3} recommendations")
            print()

            gold_map = E._load_gold_from_oracle(set(cls))
            micro = {n: [0, 0, 0] for n in ORDER}
            macro = {n: [] for n in ORDER}

            for i, pid in enumerate(sorted(gold_map), 1):
                gold = gold_map[pid]
                system = {r["recId"] for r in
                          E._rows(s, E.Q_SYSTEM_APPLICABLE, pid=pid, gate=E.GATE_CUI)}
                for name, subset in groups.items():
                    g, y = gold & subset, system & subset
                    tp, fp, fn = len(g & y), len(y - g), len(g - y)
                    micro[name][0] += tp
                    micro[name][1] += fp
                    micro[name][2] += fn
                    macro[name].append(E._prf(tp, fp, fn))
                if i % 150 == 0:
                    print(f"  ... {i}/{len(gold_map)}", file=sys.stderr)
    finally:
        drv.close()

    n = len(macro["ALL"])
    print("=" * 80)
    print(f"CONCORDANCE BY DISCRIMINATION CLASS   ({n} patients, {arm})")
    print("=" * 80)
    print(f"{'class':<17}{'recs':>5}{'P':>9}{'R':>8}{'F1':>8}    {'tp':>7}{'fp':>7}{'fn':>7}")
    for name in ORDER:
        tp, fp, fn = micro[name]
        p, r, f = E._prf(tp, fp, fn)
        print(f"{name:<17}{len(groups[name]):>5}{p:>9.3f}{r:>8.3f}{f:>8.3f}"
              f"    {tp:>7}{fp:>7}{fn:>7}")
    print("\nmacro-averaged over patients:")
    print(f"{'class':<17}{'P':>9}{'R':>8}{'F1':>8}")
    for name in ORDER:
        rows = macro[name]
        mp = sum(x[0] for x in rows) / len(rows)
        mr = sum(x[1] for x in rows) / len(rows)
        mf = sum(x[2] for x in rows) / len(rows)
        print(f"{name:<17}{mp:>9.3f}{mr:>8.3f}{mf:>8.3f}")


if __name__ == "__main__":
    main()
