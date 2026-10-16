r"""
make_worksheets.py
=======================
Generate the manual-labelling packet for the FHIR CRS evaluation:
  eval/worksheet_<pid>.csv  -- the 68 positive recs with an empty gold_applicable
  eval/clinical_<pid>.md    -- the patient's conditions + medications + OBSERVATIONS

The observations (LVEF / BMI / LDL / BP / smoking) are the FHIR addition: the human
cannot label the observation-gated recs (BB:1 LVEF<=40, WM:2/3 BMI, SGLT2:4/6,
BPM:1, RAAI) without them, and the thesis worksheet omitted them (observations
weren't loaded then). Aggregation matches the oracle (worst-ever labs, most-recent BP).

After filling gold_applicable (and gold_true_contra in the safety worksheet):
  build_gold_labels.py                 -> eval/gold_labels.csv
  silver_oracle.py validate         -> oracle-vs-manual agreement + Cohen's kappa
  crs_eval.py score               -> concordance vs the manual gold

Usage (driver venv):
    set NEO4J_PASSWORD=... && set NEO4J_DATABASE=sihdfhir
    .../.venv/Scripts/python.exe make_worksheets.py <pid> [<pid> ...]
"""

import os
import sys
import csv

os.environ.setdefault("NEO4J_DATABASE", "sihdfhir")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")

import crs_eval as E  # noqa: E402  (FHIR-native after consolidation)
import obs_gate  # noqa: E402
import nsaid_csv  # noqa: E402  (APT:10 chronicity from CSV course durations)

EVAL_DIR = "eval"

# The clinical picture shows the patient's COMPLETE record (every condition and
# medication, CCD-related or not) so the labeller can apply the rulebook's
# "full record" rule. These are deliberately broader than the CRS's own queries:
#  - conditions: every coded condition (deduped by display), any coding system.
#  - medications: BOTH the inline medicationCodeableConcept (-> :Code) AND the
#    medicationReference form (-> :Medication -> :CODE -> :Code). The CRS's
#    inline-only med query silently drops the referenced ones (~9/patient here),
#    which would also make the warfarin/OAC flag miss a referenced anticoagulant.
Q_ALL_CONDITIONS = """
MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
RETURN DISTINCT k.display AS name ORDER BY name
"""
Q_ALL_MEDS = """
MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(x)
OPTIONAL MATCH (x)-[:CODE]->(mc:Code)
WITH CASE WHEN x:Code THEN x.display ELSE mc.display END AS name
WHERE name IS NOT NULL
RETURN DISTINCT name ORDER BY name
"""
# Key cardiac procedures/interventions. PCI is procedure-ONLY in Synthea (never a
# condition) and drives APT:2 / APT:11 / CR:1:1, so the labeller cannot see it in the
# conditions list -- it must be shown explicitly. (MI-history and CABG-history ARE
# conditions and appear in the conditions list.)
SNOMED = "http://snomed.info/sct"
Q_PROCEDURES = f"""
MATCH (p:Patient {{uid:$pid}})<-[:SUBJECT]-(:Procedure)-[:CODE]->(k:Code)
WHERE k.system = '{SNOMED}'
  AND k.display =~ '(?i).*(percutaneous coronary|coronary artery bypass|valve|transplant|stent|angioplasty|defibrillator|pacemaker|cardiac ablation).*'
RETURN DISTINCT k.code AS code, k.display AS name ORDER BY name
"""


def generate(pid, session, clinical_only=False):
    conds = [r["name"] for r in session.run(Q_ALL_CONDITIONS, pid=pid)]
    meds = [r["name"] for r in session.run(Q_ALL_MEDS, pid=pid)]
    recs = [r.data() for r in session.run(E.Q_ALL_POSITIVE, pid=pid, gate=E.GATE_CUI)]
    procs = [r.data() for r in session.run(Q_PROCEDURES, pid=pid)]
    pci = any(r["code"] == "415070008" for r in procs)
    f = obs_gate.features(session, pid)

    # Anticoagulation flags: warfarin (asked for explicitly) + the full needs_oac
    # picture, which drives APT:1 (fires only WITHOUT an OAC indication) and
    # APT:11-16 (fire only if the patient REQUIRES oral anticoagulation). Match the
    # oracle's OAC list + AF-as-OAC-indication logic (silver_oracle.OACS / needs_oac).
    OACS = ("warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban")
    low_meds = [m.lower() for m in meds]
    low_conds = [c.lower() for c in conds]
    warfarin = any("warfarin" in m for m in low_meds)
    any_oac = any(o in m for m in low_meds for o in OACS)
    af = any(("atrial fibrillation" in c or "atrial flutter" in c) for c in low_conds)

    # APT:10 chronic-NSAID: the full operational rule needs course STOP dates, which
    # FHIR drops -- sourced from the CSV (nsaid_csv), the same source the oracle uses.
    nsaid = nsaid_csv.chronicity(pid)

    ws = os.path.join(EVAL_DIR, f"worksheet_{pid}.csv")
    if not clinical_only:
        with open(ws, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["recId", "cor", "gold_applicable", "conditionHint", "text"])
            for r in recs:
                hint = "; ".join([h for h in r["conditionHint"] if h]) or "(universal)"
                w.writerow([r["recId"], r["cor"], "", hint, r["text"]])

    cp = os.path.join(EVAL_DIR, f"clinical_{pid}.md")
    with open(cp, "w", encoding="utf-8") as fh:
        fh.write(f"PATIENT {pid}\n")
        fh.write("Label each rec in worksheet_%s.csv against THIS record + the guideline text.\n\n" % pid)
        fh.write("OBSERVATIONS (needed for the observation-gated recs):\n")
        fh.write(f"  LVEF (worst/min)   : {f['lvef_min']}\n")
        fh.write(f"  BMI  (max)         : {f['bmi_max']}\n")
        fh.write(f"  LDL  (max)         : {f['ldl_max']}\n")
        fh.write(f"  TG   (max)         : {f['tg_max']}   (LIPID:9: LDL<100 & TG 150-499)\n")
        fh.write(f"  BP   (most-recent) : {f['sbp']}/{f['dbp']}\n")
        fh.write(f"  smoker (recent)    : {f['smoker_recent']}\n\n")
        fh.write("ANTICOAGULATION (drives APT:1, APT:11-16):\n")
        fh.write(f"  warfarin            : {'yes' if warfarin else 'no'}\n")
        fh.write(f"  any OAC             : {'yes' if any_oac else 'no'}"
                 "   (warfarin/apixaban/rivaroxaban/dabigatran/edoxaban)\n")
        fh.write(f"  atrial fibrillation : {'yes' if af else 'no'}\n")
        fh.write(f"  -> requires OAC     : {'yes' if (any_oac or af) else 'no'}"
                 "   (on an OAC OR has AF)\n\n")
        fh.write("NSAID USE (APT:10 chronic NSAID -- from CSV course durations, not the graph):\n")
        fh.write(f"  courses (episodes)  : {nsaid['courses']}\n")
        fh.write(f"  cumulative days     : {nsaid['cumulative_days']}\n")
        fh.write(f"  longest course (d)  : {nsaid['max_course_days']}\n")
        fh.write(f"  -> chronic NSAID    : {'yes' if nsaid['chronic'] else 'no'}"
                 "   (>90d cumulative OR >=3 courses OR any single >30d)\n\n")
        fh.write("PROCEDURES / INTERVENTIONS (PCI is procedure-only -> drives APT:2, APT:11, CR:1:1):\n")
        fh.write(f"  PCI (415070008)     : {'yes' if pci else 'no'}\n")
        if procs:
            for r in procs:
                fh.write(f"    - {r['name']}\n")
        else:
            fh.write("    (no key cardiac-intervention procedures)\n")
        fh.write("\n")
        fh.write(f"CONDITIONS ({len(conds)}):\n")
        for c in conds:
            fh.write(f"  - {c}\n")
        fh.write(f"\nMEDICATIONS ({len(meds)}):\n")
        for m in meds:
            fh.write(f"  - {m}\n")
    return ws, cp, len(recs)


def main():
    args = sys.argv[1:]
    clinical_only = "--clinical-only" in args   # regenerate clinical_*.txt only; keep worksheets
    pids = [a for a in args if a != "--clinical-only"]
    if not pids:
        sys.exit("Usage: make_worksheets.py [--clinical-only] <pid> [<pid> ...]")
    os.makedirs(EVAL_DIR, exist_ok=True)
    drv = E._connect()
    try:
        with drv.session(database=E.NEO4J_DATABASE) as s:
            for pid in pids:
                ws, cp, n = generate(pid, s, clinical_only=clinical_only)
                print(f"  {pid}: {'clinical only' if clinical_only else str(n)+' recs'} -> {cp}"
                      + ("" if clinical_only else f" + {ws}"))
    finally:
        drv.close()
    if clinical_only:
        print(f"\nRegenerated {len(pids)} clinical picture(s); worksheets left untouched.")
    else:
        print(f"\nWrote {len(pids)} worksheet(s) + clinical pictures to {EVAL_DIR}/.")
        print("Next: fill gold_applicable (1/0), then run the safety worksheet:")
        print("  crs_eval.py safety")


if __name__ == "__main__":
    main()
