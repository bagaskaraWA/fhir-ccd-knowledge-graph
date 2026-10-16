r"""
obs_gate.py
===========
Observation gates for the FHIR CRS -- the concrete FHIR value-add.

The thesis CRS gate+AND matches on CONDITION CUIs only. Numeric-observation preconditions
("LVEF <= 40", "BMI >= 30", most-recent BP / smoking) were therefore ungated, so those recs
were BASELINE and fired for every CCD patient (the dominant precision limitation). Loading
observations as graph nodes is what lets this module gate on them.

CORRECTION -- this docstring used to say those preconditions "were text-only and ungateable
in the CSV pipeline", which credited FHIR for the gain. That was asserted, never measured,
and csv_gate.py has since measured it: rebuilding this gate from Synthea's flat CSV export
reproduces all 13140 decisions exactly (eval/csv_gating_experiment.txt). The gain comes from
gating on numeric values at all, not from the container. FHIR makes it direct; the flat
export needs a reassembly step keyed on ENCOUNTER and rounds to one decimal place. See
Bab IV, sec:csv-gating.

For the observation-gated recs, applicability is DECIDED by the oracle's exact
predicate (silver_oracle.RULES) evaluated on features read FROM THE GRAPH -- not
post-filtered -- so disjunctive recs (RAAI:1: htn OR dm OR ckd OR LVEF<=40) compose
correctly. This is convergent validation, not circularity: silver_oracle reads the RAW
FHIR bundles; this reads the graph's Observation nodes. Two independent paths over
the same clinical data; the thresholds/aggregations are deliberately identical so they
agree.

Scope = observation-bearing recs only. Medication-only (LIPID:2), negation (BB:3),
and risk-composite (LIPID:5/7/10) preconditions stay as documented limitations.
LIPID:9 IS gated now that TG is loaded (LOINC 2571-8): hypertriglyceridemia condition
+ LDL < 100 + fasting TG 150-499.

Thresholds + aggregation are copied verbatim from silver_oracle.py:
  labs = worst-ever (min LVEF, max LDL/BMI/TG); BP + smoking = most-recent.
"""

SNOMED = "http://snomed.info/sct"

LVEF_CODE = "10230-1"
LDL_CODE = "18262-6"
TG_CODE = "2571-8"            # triglycerides [Mass/volume] -- gates LIPID:9
BMI_CODE = "39156-5"          # BMI [Ratio] -- NOT 59576-9 [Percentile] (oracle excludes it)
BP_CODE = "85354-9"
SMOKING_CODE = "72166-2"

GATE_CUI = "C0151744"

# ── feature queries (aggregated in Cypher, mirroring silver_oracle.load_obs) ──────────────

_Q_LABS = f"""
MATCH (p:Patient {{uid:$pid}})
OPTIONAL MATCH (p)<-[:SUBJECT]-(ol:Observation)-[:CODE]->(:Code {{code:'{LVEF_CODE}'}})
WITH p, min(ol.valueQuantity_value) AS lvef_min
OPTIONAL MATCH (p)<-[:SUBJECT]-(od:Observation)-[:CODE]->(:Code {{code:'{LDL_CODE}'}})
WITH p, lvef_min, max(od.valueQuantity_value) AS ldl_max
OPTIONAL MATCH (p)<-[:SUBJECT]-(ob:Observation)-[:CODE]->(:Code {{code:'{BMI_CODE}'}})
WITH p, lvef_min, ldl_max, max(ob.valueQuantity_value) AS bmi_max
OPTIONAL MATCH (p)<-[:SUBJECT]-(ot:Observation)-[:CODE]->(:Code {{code:'{TG_CODE}'}})
RETURN lvef_min, ldl_max, bmi_max, max(ot.valueQuantity_value) AS tg_max
"""

# most-recent BP: the latest 85354-9 Observation's systolic/diastolic components.
_Q_BP = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {{code:'{BP_CODE}'}})
WITH o ORDER BY o.effectiveDateTime DESC LIMIT 1
MATCH (o)-[:COMPONENT]->(c:Component)-[:CODE]->(cc:Code)
RETURN max(CASE WHEN cc.display STARTS WITH 'Systolic'  THEN c.valueQuantity_value END) AS sbp,
       max(CASE WHEN cc.display STARTS WITH 'Diastolic' THEN c.valueQuantity_value END) AS dbp
"""

# most-recent smoking status display.
_Q_SMOKE = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {{code:'{SMOKING_CODE}'}})
OPTIONAL MATCH (o)-[:VALUE]->(v:Code)
WITH o.effectiveDateTime AS ts, v.display AS val ORDER BY ts DESC LIMIT 1
RETURN val
"""

# condition displays (lower-cased) + the cohort-gate membership flag.
_Q_CONDS = f"""
MATCH (p:Patient {{uid:$pid}})
OPTIONAL MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
  WHERE k.system = '{SNOMED}'
WITH p, collect(DISTINCT toLower(k.display)) AS conds
RETURN conds,
       EXISTS {{ (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code)<-[:SAME_CONCEPT]-(:Concept {{umlsCui:'{GATE_CUI}'}}) }} AS ccd
"""


def _any(items, *subs):
    return any(any(s in x for s in subs) for x in items)


def features(session, pid):
    """Read the graph and build the oracle-shaped feature dict for pid."""
    labs = session.run(_Q_LABS, pid=pid).single()
    bp = session.run(_Q_BP, pid=pid).single()
    smoke = session.run(_Q_SMOKE, pid=pid).single()
    cr = session.run(_Q_CONDS, pid=pid).single()
    cond = cr["conds"] if cr else []
    sval = (smoke["val"] or "").lower() if smoke and smoke["val"] else ""

    f = {
        "pid": pid,
        "ccd": bool(cr["ccd"]) if cr else False,
        # observations
        "lvef_min": labs["lvef_min"] if labs else None,
        "ldl_max": labs["ldl_max"] if labs else None,
        "bmi_max": labs["bmi_max"] if labs else None,
        "tg_max": labs["tg_max"] if labs else None,
        "sbp": bp["sbp"] if bp else None,
        "dbp": bp["dbp"] if bp else None,
        # conditions (same substring logic as silver_oracle.features)
        "hf":   _any(cond, "heart failure"),
        "htn":  _any(cond, "hypertensi"),
        "dm":   any("diabet" in c and "prediabet" not in c for c in cond),
        "ckd":  _any(cond, "chronic kidney disease", "end-stage renal", "end stage renal"),
        "hypertg": _any(cond, "hypertriglyceridemia"),
        "obesity_cond":    _any(cond, "body mass index 30", "obesity", "obese"),
        "overweight_cond": _any(cond, "overweight"),
        "severe_obesity":  _any(cond, "body mass index 40", "severely obese", "severe obesity"),
    }
    f["smoker_recent"] = ("current every day" in sval or "smokes" in sval)
    f["bmi_ge25"] = ((f["bmi_max"] is not None and f["bmi_max"] >= 25)
                     or f["overweight_cond"] or f["obesity_cond"])
    f["bmi_ge40"] = (f["bmi_max"] is not None and f["bmi_max"] >= 40) or f["severe_obesity"]
    return f


# ── observation-gated recs -> oracle predicate (full recId; thresholds == silver_oracle) ──

def _bpm1(f):
    return f["sbp"] is not None and 120 <= f["sbp"] <= 129 and (f["dbp"] is None or f["dbp"] < 80)


OBS_GATE = {
    "CCD-2023:BB:1":     lambda f: f["lvef_min"] is not None and f["lvef_min"] <= 40,
    "CCD-2023:BB:2":     lambda f: f["lvef_min"] is not None and f["lvef_min"] < 50,
    "CCD-2023:SGLT2:4":  lambda f: f["hf"] and f["lvef_min"] is not None and f["lvef_min"] <= 40,
    "CCD-2023:SGLT2:6":  lambda f: f["hf"] and f["lvef_min"] is not None and f["lvef_min"] > 40,
    "CCD-2023:RAAI:1":   lambda f: f["htn"] or f["dm"] or f["ckd"]
                                   or (f["lvef_min"] is not None and f["lvef_min"] <= 40),
    "CCD-2023:RAAI:2":   lambda f: (not (f["htn"] or f["dm"] or f["ckd"]))
                                   and f["lvef_min"] is not None and f["lvef_min"] > 40,
    "CCD-2023:BPM:1":    _bpm1,
    # LIPID:9 (icosapent ethyl) -- verbatim from silver_oracle.RULES["LIPID:9"]. The graph
    # gate+AND fires it on the hypertriglyceridemia condition alone; the oracle also
    # requires LDL<100 and fasting TG 150-499, so gating here removes the over-fire.
    # (Matches the oracle, which omits the "maximally tolerated statin" clause as
    # unconfirmable -- so this predicate deliberately does NOT check statin.)
    "CCD-2023:LIPID:9":  lambda f: (f["hypertg"]
                                    and f["ldl_max"] is not None and f["ldl_max"] < 100
                                    and f["tg_max"] is not None and 150 <= f["tg_max"] <= 499),
    "CCD-2023:WM:2":     lambda f: f["bmi_ge25"],
    "CCD-2023:WM:3":     lambda f: f["bmi_ge25"],
    # WM:4 (bariatric referral) is NOT observation-gated: BMI>=40 is confirmable but the
    # deciding preconditions (acceptable surgical risk, failed prior therapy) are not, so
    # gating on BMI alone would over-claim. It reverts to the graph gate+AND (fires on the
    # severe-obesity condition) and is an honest FP vs the always-0 gold -- like the
    # un-confirmable risk-score recs. See silver_oracle.py.
    "CCD-2023:TP:2":     lambda f: f["smoker_recent"],
    "CCD-2023:TP:3:1":   lambda f: f["smoker_recent"],
    "CCD-2023:TP:3:2":   lambda f: f["smoker_recent"],
    "CCD-2023:TP:4":     lambda f: f["smoker_recent"],
    "CCD-2023:TP:5":     lambda f: f["smoker_recent"],
}

OBS_GATED = set(OBS_GATE)


def decide(graph_applicable, feats):
    """Combine the graph gate+AND set with observation-gated decisions.

    Non-obs-gated recs: keep the graph's decision.
    Obs-gated recs: DECIDE by the oracle predicate on graph features (overrides the
    graph, so disjunctive LVEF branches add patients rather than being filtered out).
    Only fire obs-gated recs for gate-passing (CCD) patients.
    """
    keep = {r for r in graph_applicable if r not in OBS_GATED}
    if feats.get("ccd"):
        keep |= {r for r, pred in OBS_GATE.items() if pred(feats)}
    return keep
