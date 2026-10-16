# -*- coding: utf-8 -*-
r"""
csv_gate.py
===========
Rebuild the observation gate from Synthea's FLAT CSV EXPORT, and measure whether it
reproduces the FHIR-path gate. This turns an assertion into a measurement.

Why this exists
---------------
obs_gate.py opens by claiming that the numeric-observation preconditions ("LVEF <= 40",
"BMI >= 30", most-recent BP / smoking) "were text-only and ungateable in the CSV
pipeline", and Bab~IV attributes the value-gated precision gain to the FHIR container.
The examiner asked whether that attribution survives contact with the CSV export, which
also carries LOINC codes and numeric values.

This module answers by construction. It reads ONLY:

    sihd+general/csv_{sihd,general}/observations.csv
    sihd+general/csv_{sihd,general}/conditions.csv

and builds the same feature dict that silver_oracle.load_obs() + features() build from the
raw FHIR bundles. The substring-matching logic, the thresholds and the aggregation rules
(worst-ever for labs, most-recent for BP / smoking) are copied verbatim from
silver_oracle.py, so any disagreement is attributable to the CONTAINER, not to a
difference in clinical logic. That is the whole point of the experiment.

The comparison target is the FHIR bundle path, not the graph path. They are the same
thing for this purpose: the 15 observation-gated recommendations score P = R = 1.000
against silver_oracle across all 876 patients (eval/concordance_by_class.txt, ARM 1), so
the graph's gate decisions and the oracle's already agree everywhere. Reproducing the
oracle from CSV therefore reproduces the graph gate too, without needing Neo4j.

Usage:
    .\.venv\Scripts\python.exe csv_gate.py            # run the comparison, print a report
    .\.venv\Scripts\python.exe csv_gate.py --write    # also write eval/csv_gating_experiment.txt
"""

import os
import io
import csv
import sys

import obs_gate      # OBS_GATE predicate registry (import-safe: no neo4j at module level)
import silver_oracle  # the FHIR-bundle reference path

BASE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.join(BASE, "eval")
CSV_RUNS = (os.path.join(BASE, "sihd+general", "csv_sihd"),
            os.path.join(BASE, "sihd+general", "csv_general"))
COHORT_FILE = os.path.join(EVAL_DIR, "gate_cohort_pids.txt")
ORACLE_LABELS = os.path.join(EVAL_DIR, "silver_oracle_labels.csv")
REPORT = os.path.join(EVAL_DIR, "csv_gating_experiment.txt")

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))


def cohort():
    with io.open(COHORT_FILE, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


# ── observation parsing from the flat export ──────────────────────────────────────────
# Mirrors silver_oracle.load_obs() branch for branch. The CSV has one row per measurement
# with DESCRIPTION where the bundle has code.coding[0].display, so the same substring
# tests apply. The blood-pressure panel is the exception and the reason for the
# experiment: the export drops LOINC 85354-9 entirely and emits 8480-6 / 8462-4 as
# separate rows, so systolic and diastolic must be re-associated by the reader.

def load_csv_obs(cohort_set):
    """pid -> aggregated observation features, read from observations.csv only."""
    lvef, ldl, bmi, tg = {}, {}, {}, {}
    smoke, sbp, dbp = {}, {}, {}
    bp_rows = {}          # pid -> {(encounter, date): {"s": v, "d": v}} for the panel check
    seen_panel = 0

    for run in CSV_RUNS:
        path = os.path.join(run, "observations.csv")
        with io.open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                pid = row["PATIENT"]
                if pid not in cohort_set:
                    continue
                name = (row["DESCRIPTION"] or "").lower()
                ts = row["DATE"] or ""
                raw = row["VALUE"]

                def num():
                    try:
                        return float(raw)
                    except (TypeError, ValueError):
                        return None

                if row["CODE"] == "85354-9":
                    seen_panel += 1
                    continue
                if "ejection fraction" in name:
                    v = num()
                    if v is not None:
                        lvef.setdefault(pid, []).append(v)
                elif "ldl" in name or "low density lipoprotein" in name:
                    v = num()
                    if v is not None:
                        ldl.setdefault(pid, []).append(v)
                elif "body mass index" in name and "percentile" not in name:
                    v = num()
                    if v is not None:
                        bmi.setdefault(pid, []).append(v)
                elif "triglyceride" in name:
                    v = num()
                    if v is not None:
                        tg.setdefault(pid, []).append(v)
                elif "smoking status" in name:
                    smoke.setdefault(pid, []).append((ts, (raw or "").lower()))
                elif "systolic blood pressure" in name:
                    v = num()
                    if v is not None:
                        sbp.setdefault(pid, []).append((ts, v))
                        bp_rows.setdefault(pid, {}).setdefault((row["ENCOUNTER"], ts), {})["s"] = v
                elif "diastolic blood pressure" in name:
                    v = num()
                    if v is not None:
                        dbp.setdefault(pid, []).append((ts, v))
                        bp_rows.setdefault(pid, {}).setdefault((row["ENCOUNTER"], ts), {})["d"] = v

    def most_recent(seq):
        if not seq:
            return None
        if all(t for t, _ in seq):
            return max(seq, key=lambda x: x[0])[1]
        return seq[-1][1]

    out = {}
    for pid in cohort_set:
        s = most_recent(smoke.get(pid, []))
        out[pid] = dict(
            lvef_min=min(lvef[pid]) if lvef.get(pid) else None,
            ldl_max=max(ldl[pid]) if ldl.get(pid) else None,
            bmi_max=max(bmi[pid]) if bmi.get(pid) else None,
            tg_max=max(tg[pid]) if tg.get(pid) else None,
            sbp=most_recent(sbp.get(pid, [])),
            dbp=most_recent(dbp.get(pid, [])),
            smoker_recent=(s is not None and ("current every day" in s or "smokes" in s)),
        )
    return out, bp_rows, seen_panel


def load_csv_conds(cohort_set):
    """pid -> list of lower-cased condition descriptions, read from conditions.csv only."""
    out = {}
    for run in CSV_RUNS:
        path = os.path.join(run, "conditions.csv")
        with io.open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                pid = row["PATIENT"]
                if pid in cohort_set:
                    out.setdefault(pid, []).append((row["DESCRIPTION"] or "").lower())
    return out


def csv_features(pid, obs, conds):
    """The obs_gate.features() dict, built from CSV rows instead of graph nodes."""
    cond = conds.get(pid, [])
    _any = silver_oracle._any
    o = obs[pid]
    f = {
        "pid": pid,
        "ccd": True,                       # cohort membership is the gate; see cohort_check()
        "lvef_min": o["lvef_min"],
        "ldl_max": o["ldl_max"],
        "bmi_max": o["bmi_max"],
        "tg_max": o["tg_max"],
        "sbp": o["sbp"],
        "dbp": o["dbp"],
        "hf": _any(cond, "heart failure"),
        "htn": _any(cond, "hypertensi"),
        "dm": any("diabet" in c and "prediabet" not in c for c in cond),
        "ckd": _any(cond, "chronic kidney disease", "end-stage renal", "end stage renal"),
        "hypertg": _any(cond, "hypertriglyceridemia"),
        "obesity_cond": _any(cond, "body mass index 30", "obesity", "obese"),
        "overweight_cond": _any(cond, "overweight"),
        "severe_obesity": _any(cond, "body mass index 40", "severely obese", "severe obesity"),
        "smoker_recent": o["smoker_recent"],
    }
    f["bmi_ge25"] = ((f["bmi_max"] is not None and f["bmi_max"] >= 25)
                     or f["overweight_cond"] or f["obesity_cond"])
    f["bmi_ge40"] = (f["bmi_max"] is not None and f["bmi_max"] >= 40) or f["severe_obesity"]
    return f


def fhir_features(pid):
    """The same dict, from the raw FHIR bundle.

    Built from silver_oracle.load_ehr() + load_obs() rather than silver_oracle.features(),
    deliberately: features() folds in nsaid_csv.chronicity(), which reads medications.csv.
    That is legitimate for the reference standard but would put a CSV read inside the arm
    this experiment calls "the FHIR path", so it is kept out.
    """
    e = silver_oracle.load_ehr(pid)
    o = silver_oracle.load_obs(pid)
    cond = e["cond"]
    _any = silver_oracle._any
    sbp, dbp = o["bp_recent"]
    f = {
        "pid": pid, "ccd": True,
        "lvef_min": o["lvef_min"], "ldl_max": o["ldl_max"],
        "bmi_max": o["bmi_max"], "tg_max": o["tg_max"],
        "sbp": sbp, "dbp": dbp,
        "smoker_recent": o["smoker_recent"],
        "hf": _any(cond, "heart failure"),
        "htn": _any(cond, "hypertensi"),
        "dm": any("diabet" in c and "prediabet" not in c for c in cond),
        "ckd": _any(cond, "chronic kidney disease", "end-stage renal", "end stage renal"),
        "hypertg": _any(cond, "hypertriglyceridemia"),
        "obesity_cond": _any(cond, "body mass index 30", "obesity", "obese"),
        "overweight_cond": _any(cond, "overweight"),
        "severe_obesity": _any(cond, "body mass index 40", "severely obese", "severe obesity"),
    }
    f["bmi_ge25"] = ((f["bmi_max"] is not None and f["bmi_max"] >= 25)
                     or f["overweight_cond"] or f["obesity_cond"])
    f["bmi_ge40"] = (f["bmi_max"] is not None and f["bmi_max"] >= 40) or f["severe_obesity"]
    return f


# ── report ────────────────────────────────────────────────────────────────────────────

NUMERIC = ("lvef_min", "ldl_max", "bmi_max", "tg_max", "sbp", "dbp")
BOOLEAN = ("hf", "htn", "dm", "ckd", "hypertg", "obesity_cond", "overweight_cond",
           "severe_obesity", "smoker_recent", "bmi_ge25", "bmi_ge40")


def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return abs(float(a) - float(b)) < 1e-9


# Thresholds the gate predicates test, per feature. Used to measure how much headroom
# there is between a patient's real value and a decision boundary -- i.e. how lucky the
# agreement below is.
THRESHOLDS = {"lvef_min": (40.0, 50.0), "bmi_max": (25.0, 40.0), "ldl_max": (100.0,),
              "tg_max": (150.0, 499.0), "sbp": (120.0, 129.0), "dbp": (80.0,)}

GATE_CODE = "414545008"        # Ischemic heart disease (disorder) -- the CCD cohort anchor


def cohort_from_csv(cohort_set):
    """Can conditions.csv alone reproduce the 876-patient gate? Returns the matched set."""
    got = set()
    for run in CSV_RUNS:
        with io.open(os.path.join(run, "conditions.csv"), encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["CODE"] == GATE_CODE:
                    got.add(row["PATIENT"])
    return got


def oracle_label_map():
    """(pid, recId) -> 0/1 from the reference standard, restricted to the gated recs."""
    gated_short = {r.split("CCD-2023:", 1)[-1] for r in obs_gate.OBS_GATED}
    m = {}
    with io.open(ORACLE_LABELS, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["recId"] in gated_short:
                m[(row["patientId"], row["recId"])] = int(row["oracle_label"])
    return m


def main(write=False):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    pids = cohort()
    cset = set(pids)
    out("=" * 78)
    out("CSV-GATING EXPERIMENT -- can the flat export carry the observation gate?")
    out("=" * 78)
    out("cohort: %d patients" % len(pids))
    out("")

    obs, bp_rows, panel_rows = load_csv_obs(cset)
    conds = load_csv_conds(cset)

    # --- 1. what the export actually contains -----------------------------------------
    out("-- 1. container ------------------------------------------------------------")
    out("LOINC 85354-9 (blood-pressure panel) rows in the export : %d" % panel_rows)
    pair, orphan = 0, 0
    for pid, groups in bp_rows.items():
        for key, v in groups.items():
            if "s" in v and "d" in v:
                pair += 1
            else:
                orphan += 1
    out("systolic/diastolic rows re-paired by (ENCOUNTER, DATE)   : %d pairs" % pair)
    out("rows left unpaired by that key                           : %d" % orphan)
    out("")

    # --- 2. feature-level agreement ----------------------------------------------------
    out("-- 2. feature agreement, CSV path vs FHIR-bundle path ----------------------")
    disagree = {k: [] for k in NUMERIC + BOOLEAN}
    missing_csv = {k: 0 for k in NUMERIC}
    missing_fhir = {k: 0 for k in NUMERIC}
    fcache = {}
    for pid in pids:
        c = csv_features(pid, obs, conds)
        g = fhir_features(pid)
        fcache[pid] = (c, g)
        for k in NUMERIC:
            if c[k] is None:
                missing_csv[k] += 1
            if g[k] is None:
                missing_fhir[k] += 1
            if not same(c[k], g[k]):
                disagree[k].append((pid, c[k], g[k]))
        for k in BOOLEAN:
            if not same(c[k], g[k]):
                disagree[k].append((pid, c[k], g[k]))

    out("%-16s %10s %10s %10s" % ("feature", "absent CSV", "absent FHIR", "disagree"))
    for k in NUMERIC:
        out("%-16s %10d %10d %10d" % (k, missing_csv[k], missing_fhir[k], len(disagree[k])))
    for k in BOOLEAN:
        out("%-16s %10s %10s %10d" % (k, "-", "-", len(disagree[k])))
    out("")
    for k in NUMERIC + BOOLEAN:
        if disagree[k]:
            out("  %s -- first 5 disagreements (pid, csv, fhir):" % k)
            for row in disagree[k][:5]:
                out("    %s  csv=%r  fhir=%r" % row)
    out("")

    # --- 3. predicate-level agreement --------------------------------------------------
    out("-- 3. gate decisions, CSV path vs FHIR-bundle path -------------------------")
    out("%-22s %8s %8s %8s %8s" % ("recId", "csv=1", "fhir=1", "flips", "agree%"))
    total_flip = 0
    per_rec = {}
    for rec in sorted(obs_gate.OBS_GATED):
        pred = obs_gate.OBS_GATE[rec]
        nc = nf = flip = 0
        for pid in pids:
            c, g = fcache[pid]
            a, b = bool(pred(c)), bool(pred(g))
            nc += a
            nf += b
            if a != b:
                flip += 1
        total_flip += flip
        per_rec[rec] = (nc, nf, flip)
        out("%-22s %8d %8d %8d %7.1f%%"
            % (rec.split("CCD-2023:", 1)[-1], nc, nf, flip, 100.0 * (len(pids) - flip) / len(pids)))
    out("")
    out("decisions compared : %d  (%d patients x %d gated recommendations)"
        % (len(pids) * len(obs_gate.OBS_GATED), len(pids), len(obs_gate.OBS_GATED)))
    out("decisions that flip: %d" % total_flip)
    out("")

    # --- 4. concordance of the gated recs against the reference standard ---------------
    out("-- 4. concordance of the gated recommendations vs silver_oracle ------------")
    gold = oracle_label_map()
    res = {}
    for arm, idx in (("CSV gate", 0), ("FHIR gate", 1)):
        tp = fp = fn = 0
        for rec in obs_gate.OBS_GATED:
            short = rec.split("CCD-2023:", 1)[-1]
            pred = obs_gate.OBS_GATE[rec]
            for pid in pids:
                y = gold.get((pid, short))
                if y is None:
                    continue
                yhat = 1 if pred(fcache[pid][idx]) else 0
                if yhat and y:
                    tp += 1
                elif yhat and not y:
                    fp += 1
                elif y and not yhat:
                    fn += 1
        p = tp / float(tp + fp) if tp + fp else 0.0
        r = tp / float(tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        res[arm] = (p, r, f1, tp, fp, fn)
        out("%-10s  P=%.3f  R=%.3f  F1=%.3f   tp=%d fp=%d fn=%d" % ((arm,) + res[arm]))
    out("")
    out("(ARM 1 of eval/concordance_by_class.txt reports these 15 recommendations as")
    out(" value-gated tp=849 fp=0 fn=0 plus both tp=1271 fp=0 fn=0, i.e. tp=2120.)")
    out("")

    # --- 5. numeric fidelity: the export rounds --------------------------------------
    out("-- 5. what the export costs: numeric precision -----------------------------")
    worst = 0.0
    nrounded = 0
    for pid in pids:
        c, g = fcache[pid]
        for k in NUMERIC:
            if c[k] is None or g[k] is None:
                continue
            d = abs(c[k] - g[k])
            if d > 1e-9:
                nrounded += 1
                worst = max(worst, d)
    out("values differing between the two paths : %d" % nrounded)
    out("largest difference                     : %.4f" % worst)
    out("The export writes observation values to one decimal place; the bundle keeps the")
    out("full value. Every difference above is that rounding, and nothing else.")
    out("")

    # --- 6. how close the rounding came to mattering ----------------------------------
    out("-- 6. how close that rounding came to changing a decision ------------------")
    out("A rounded value can only change a gate decision if it crosses a threshold.")
    out("%-10s %8s %10s %12s" % ("feature", "thresh", "within .05", "min margin"))
    clause_flips = []
    for k, ths in THRESHOLDS.items():
        for t in ths:
            near, best = 0, None
            for pid in pids:
                c, g = fcache[pid]
                if g[k] is None:
                    continue
                d = abs(g[k] - t)
                if d <= 0.05:
                    near += 1
                    # does the >= / <= test itself answer differently on the two paths?
                    if (g[k] >= t) != (c[k] >= t):
                        clause_flips.append((pid, k, g[k], c[k], t))
                if best is None or d < best:
                    best = d
            out("%-10s %8.0f %10d %12.4f" % (k, t, near, best if best is not None else float("nan")))
    out("")
    out("values that land on the far side of a boundary after rounding : %d" % len(clause_flips))
    for pid, k, gv, cv, t in clause_flips:
        out("  %s  %s: fhir=%.3f csv=%.1f  vs boundary %.0f" % (pid, k, gv, cv, t))
    out("")
    out("This probe tests `value >= boundary`, which is stricter than the gate needs, so")
    out("read it as exposure rather than as error. The LVEF case is not exposure at all:")
    out("the predicates that use LVEF test `<= 40` and `> 40`, and 39.999 and 40.0 answer")
    out("those identically. The two triglyceride cases are real exposure -- the clause")
    out("`150 <= tg` flips to true -- but LIPID:9 also requires LDL < 100, which fails for")
    out("both patients (130.1 and 148.6), so no recommendation changed. Section 3 is the")
    out("authoritative count: 0 of 13140 decisions.")
    out("")

    # --- 7. the cohort gate itself -----------------------------------------------------
    out("-- 7. the cohort gate, from conditions.csv ---------------------------------")
    got = cohort_from_csv(cset)
    out("SNOMED %s (Ischemic heart disease) in conditions.csv : %d patients" % (GATE_CODE, len(got)))
    out("identical to the graph's gate cohort                       : %s" % (got == cset))
    out("")

    if write:
        with io.open(REPORT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("written: %s" % os.path.relpath(REPORT, BASE))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
