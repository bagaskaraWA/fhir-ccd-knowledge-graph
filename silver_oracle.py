r"""
silver_oracle.py
==============
Fully-automated, CRS-INDEPENDENT rule-based reference standard ("gold oracle") for
the CCD decision-support evaluation.

Why this exists / the load-bearing property
--------------------------------------------
The evaluation compares the CRS's applicable-recommendation set against a reference
("gold") label per patient x recommendation. For that comparison to be meaningful, the
reference MUST be independent of the system under test. This oracle achieves that by
labelling from the RAW patient record --

    patient ehr/<pid>.csv          (conditions / medications / procedures / careplans)
    sample_observations/observations_<pid>.csv   (LVEF / LDL / BMI / TG / BP / smoking)

-- and encoding the guideline TEXT logic directly. It NEVER reads Neo4j, never uses the
CRS's gate+AND / bridgeable-CUI output. It therefore knows things the CRS cannot see
(observations, PCI-as-procedure, text-only preconditions), which is precisely what lets
false positives/negatives appear so Precision/Recall stay informative.

  * If you ever wire this to the graph's gate+AND output, the evaluation becomes CIRCULAR
    (system == gold by construction, Precision -> 1.0). Do not. Keep it reading raw files.

Un-encodable clauses -> documented DEFAULT POLICIES (below), applied uniformly. That makes
this a *rule-based reference standard* (some reviewers call an automated reference a
"silver standard"); validate it against the manual labels with --validate and report
agreement + Cohen's kappa so it is a *validated* proxy for the manual gold.

Runs in .venv (stdlib only: csv/os/glob/argparse/statistics).
Usage:
    .\.venv\Scripts\python.exe silver_oracle.py label                 # -> eval/silver_oracle_labels.csv
    .\.venv\Scripts\python.exe silver_oracle.py label --pid <id>      # one patient, verbose
    .\.venv\Scripts\python.exe silver_oracle.py validate             # vs manual labels + kappa
"""

import os
import csv
import json
import glob
import argparse
import functools

import nsaid_csv  # NSAID course durations (APT:10) -- from the CSV, which FHIR drops

# ── paths ─────────────────────────────────────────────────────────────────────────────
# FHIR-native: labels are read from the raw Synthea FHIR BUNDLES (one per patient),
# NOT the CSV dumps. Non-circularity is preserved -- this reads the raw bundles,
# never Neo4j / the CRS output. One bundle carries conditions + medications +
# procedures + careplans + observations, so the old CSV readers, the separate
# observations.csv, and the MED_CSV juggling are all gone. The ONE exception is NSAID
# course durations (APT:10), which the FHIR export omits -- sourced from the CSV via
# nsaid_csv (still raw Synthea ground truth, never the CRS output, so non-circular).
BASE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.join(BASE, "eval")
OUT_CSV = os.path.join(EVAL_DIR, "silver_oracle_labels.csv")
# consolidated manual labels for --validate: columns patientId, recId, gold (0/1)
MANUAL_LABELS = os.path.join(EVAL_DIR, "gold_labels.csv")

FHIR_DIR = os.environ.get("FHIR_DIR", os.path.join(BASE, "sihd+general", "fhir"))
GATE_CODE = "414545008"   # Ischemic heart disease -> the CRS gate cohort


def _bundle_index():
    idx = {}
    for p in glob.glob(os.path.join(FHIR_DIR, "*.json")):
        base = os.path.basename(p)
        if base.startswith(("hospital", "practitioner")):
            continue
        idx[base[:-5].split("_")[-1]] = p        # trailing _-segment before .json
    return idx


BUNDLES = _bundle_index()


@functools.lru_cache(maxsize=2)
def _load(pid):
    with open(BUNDLES[pid], encoding="utf-8") as f:
        return json.load(f)

# ── DEFAULT POLICIES for clauses that cannot be computed from the data ─────────────────
# (documented, applied uniformly -- report these verbatim in the thesis methodology)
POLICY_UNCONFIRMABLE = 0   # rule 3 "can't confirm -> 0": risk scores, missing labs
POLICY_UNSPECIFIED_NEGATION = 1  # rule 1 "without contraindications" is un-gateable -> applicable
# NSAID chronicity (APT:10) is DERIVED from medications.csv course durations via
# nsaid_csv.chronicity (cumulative >90d OR >=3 courses OR any single course >30d).

# ── clinical vocab (substring, lower-cased) -- gotchas baked in ────────────────────────
STATINS = ("atorvastatin", "rosuvastatin", "simvastatin", "pravastatin",
           "lovastatin", "fluvastatin", "pitavastatin")   # specific -- "statin" also matches NYSTATIN
# High-intensity = the doses expected to lower LDL-C by >=50%, per the ACC/AHA
# dose-intensity table: atorvastatin 40-80 mg and rosuvastatin 20-40 mg.
#   Grundy et al. 2018, Circulation 139(25):e1082-e1143, doi 10.1161/CIR.0000000000000625
#   Stone  et al. 2013, Circulation 129(25 Suppl 2):S1-45, doi 10.1161/01.cir.0000437738.63853.7a
#
# KNOWN GAP -- do not "fix" without re-running the whole evaluation.
#   Synthea writes rosuvastatin as "rosuvastatin calcium 20 MG Oral Tablet", so the
#   substring "rosuvastatin 20" never matches (the word `calcium` sits between), and
#   rosuvastatin 40 -- high-intensity per the table above -- is absent from the tuple
#   entirely. In practice `high_statin` is therefore true only for atorvastatin 40/80.
#   Blast radius measured on the loaded graph: of the 876 CCD patients, 801 are on some
#   statin, 16 match as high today, and 4 are on rosuvastatin 20/40 and are missed.
#   Correcting it to ("atorvastatin 40", "atorvastatin 80", "rosuvastatin calcium 20",
#   "rosuvastatin calcium 40") would flip LIPID:2 from 1 to 0 for those 4 patients,
#   which ADDS 4 false positives against the CRS (LIPID:2 is universal on the graph
#   side), and would require regenerating silver_oracle_labels.csv and every Chapter IV
#   figure derived from it.
HIGH_INTENSITY_STATIN = ("atorvastatin 40", "atorvastatin 80", "rosuvastatin 20")
P2Y12 = ("clopidogrel", "ticagrelor", "prasugrel")
BETA_BLOCKERS = ("metoprolol", "carvedilol", "bisoprolol", "atenolol",
                 "propranolol", "nebivolol", "labetalol", "nadolol")
PDE5I = ("sildenafil", "tadalafil", "vardenafil", "avanafil")
NITRATES = ("nitroglycerin", "isosorbide")
NSAIDS = ("ibuprofen", "naproxen", "celecoxib", "diclofenac", "meloxicam",
          "indomethacin", "ketorolac", "piroxicam")
OACS = ("warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban")


# ── EHR parsing (from the FHIR bundle) ─────────────────────────────────────────────────
def load_ehr(pid):
    """Return dict of lower-cased description lists per resource kind, from the bundle.
    Medications resolve BOTH inline medicationCodeableConcept and medicationReference."""
    d = _load(pid)
    conds, meds, procs, careplans = [], [], [], []
    med_by_url = {}
    for e in d.get("entry", []):
        r = e["resource"]
        if r["resourceType"] == "Medication":
            cc = (r.get("code", {}).get("coding") or [{}])[0].get("display")
            if cc:
                med_by_url[e.get("fullUrl", "")] = cc.lower()
    for e in d.get("entry", []):
        r = e["resource"]
        rt = r["resourceType"]
        if rt == "Condition":
            for cc in r.get("code", {}).get("coding", []):
                if cc.get("display"):
                    conds.append(cc["display"].lower())
        elif rt == "MedicationRequest":
            if "medicationCodeableConcept" in r:
                for cc in r["medicationCodeableConcept"].get("coding", []):
                    if cc.get("display"):
                        meds.append(cc["display"].lower())
            elif "medicationReference" in r:
                disp = med_by_url.get(r["medicationReference"].get("reference", ""))
                if disp:
                    meds.append(disp)
        elif rt == "Procedure":
            for cc in r.get("code", {}).get("coding", []):
                if cc.get("display"):
                    procs.append(cc["display"].lower())
        elif rt == "CarePlan":
            for cat in r.get("category", []):
                for cc in cat.get("coding", []):
                    if cc.get("display"):
                        careplans.append(cc["display"].lower())
    return {"cond": conds, "med": meds, "proc": procs, "careplan": careplans}


# ── observation parsing (LVEF / LDL / BMI / TG / BP / smoking), from the bundle ─────────
def load_obs(pid):
    """Aggregated observation features from the bundle.  Worst-ever for labs (rule 4),
    most-recent for BP/smoking (the rule-4 exception).  Missing -> None."""
    d = _load(pid)
    lvef, ldl, bmi, tg = [], [], [], []
    smoking_seq, sbp_seq, dbp_seq = [], [], []
    for e in d.get("entry", []):
        r = e["resource"]
        if r["resourceType"] != "Observation":
            continue
        name = ((r.get("code", {}).get("coding") or [{}])[0].get("display") or "").lower()
        ts = r.get("effectiveDateTime", "")

        def q(res):
            v = res.get("valueQuantity", {}).get("value")
            return float(v) if v is not None else None

        if "ejection fraction" in name:
            v = q(r);  lvef.append(v) if v is not None else None
        elif "ldl" in name or "low density lipoprotein" in name:
            v = q(r);  ldl.append(v) if v is not None else None
        elif "body mass index" in name and "percentile" not in name:
            v = q(r);  bmi.append(v) if v is not None else None
        elif "triglyceride" in name:
            v = q(r);  tg.append(v) if v is not None else None
        elif "smoking status" in name:
            val = ((r.get("valueCodeableConcept", {}).get("coding") or [{}])[0].get("display") or "").lower()
            smoking_seq.append((ts, val))
        elif "component" in r:                    # BP panel -> systolic/diastolic components
            for comp in r["component"]:
                cn = ((comp.get("code", {}).get("coding") or [{}])[0].get("display") or "").lower()
                cv = comp.get("valueQuantity", {}).get("value")
                if cv is None:
                    continue
                if "systolic blood pressure" in cn:
                    sbp_seq.append((ts, float(cv)))
                elif "diastolic blood pressure" in cn:
                    dbp_seq.append((ts, float(cv)))

    def most_recent(seq):
        if not seq:
            return None
        if all(t for t, _ in seq):
            return max(seq, key=lambda x: x[0])[1]
        return seq[-1][1]

    smoke = most_recent(smoking_seq)
    return dict(
        lvef_min=min(lvef) if lvef else None,      # worst-ever = lowest EF
        ldl_max=max(ldl) if ldl else None,         # worst-ever = highest LDL
        bmi_max=max(bmi) if bmi else None,         # worst-ever = highest BMI
        tg_max=max(tg) if tg else None,
        bp_recent=(most_recent(sbp_seq), most_recent(dbp_seq)),
        smoker_recent=(smoke is not None and ("current every day" in smoke or "smokes" in smoke)),
    )


# ── NSAID chronicity for APT:10 -> nsaid_csv (CSV course durations) ─────────────────────
# The full operational rule (cumulative >90d OR >=3 courses OR any single course >30d)
# needs course STOP dates, which the FHIR bundle drops -- so it is sourced from Synthea's
# CSV export via nsaid_csv.chronicity(). Reading the CSV is not circular: it is raw
# Synthea ground truth, never the CRS output. The CRS/graph side keeps the
# >=3-prescription proxy (no stop date in FHIR); that APT:10 gap is the honest FHIR limit.


# ── feature extraction ─────────────────────────────────────────────────────────────────
def _any(items, *subs):
    return any(any(s in x for s in subs) for x in items)


def features(pid):
    e = load_ehr(pid)
    o = load_obs(pid)
    cond, med, proc = e["cond"], e["med"], e["proc"]
    f = {
        "pid": pid,
        # conditions
        "htn":   _any(cond, "hypertensi"),
        "dm":    any("diabet" in c and "prediabet" not in c for c in cond),
        "mi":    _any(cond, "myocardial infarction"),          # covers acute + "history of MI"
        "cabg":  _any(cond, "coronary artery bypass"),         # "History of CABG (situation)"
        "stroke": _any(cond, "cerebrovascular accident", "cerebral infarction",
                       "transient ischemic", "intracranial hemorrhage", "cerebral hemorrhage"),
        "ckd":   _any(cond, "chronic kidney disease", "end-stage renal", "end stage renal"),
        "pad":   _any(cond, "peripheral arterial", "peripheral vascular", "peripheral artery"),
        "hf":    _any(cond, "heart failure"),
        "hypertg": _any(cond, "hypertriglyceridemia"),
        "angina": _any(cond, "angina"),
        "refractory_angina": _any(cond, "refractory angina"),
        "scad": _any(cond, "coronary artery dissection"),
        "acs":  _any(cond, "st segment elevation", "st elevation", "preinfarction",
                     "unstable angina"),
        "obesity_cond": _any(cond, "body mass index 30", "obesity", "obese"),
        "overweight_cond": _any(cond, "overweight"),
        "severe_obesity": _any(cond, "body mass index 40", "severely obese", "severe obesity"),
        "alcohol": _any(cond, "alcohol"),
        # procedures (raw -- PCI is procedure-only in Synthea; angiography != PCI)
        "pci":  any("percutaneous coronary intervention" in p for p in proc),
        "cabg_proc": any("coronary artery bypass grafting" in p for p in proc),
        # medications
        "aspirin": _any(med, "aspirin"),
        "clopidogrel": _any(med, "clopidogrel"),
        "prasugrel": _any(med, "prasugrel"),
        "p2y12": _any(med, *P2Y12),
        "statin": _any(med, *STATINS),
        "high_statin": _any(med, *HIGH_INTENSITY_STATIN),
        "ezetimibe": _any(med, "ezetimibe"),
        "beta_blocker": _any(med, *BETA_BLOCKERS),
        "pde5i": _any(med, *PDE5I),
        "nitrate": _any(med, *NITRATES),
        "nsaid": _any(med, *NSAIDS),
        "oac": _any(med, *OACS),
        "af": _any(cond, "atrial fibrillation", "atrial flutter"),
        # observations
        **o,
    }
    f["dapt"] = f["aspirin"] and f["p2y12"]
    f["nsaid_chronic"] = nsaid_csv.chronicity(pid)["chronic"]   # CSV course durations
    f["needs_oac"] = f["oac"] or f["af"]        # proxy for "requires oral anticoagulation"
    f["bmi_ge30"] = (f["bmi_max"] is not None and f["bmi_max"] >= 30) or f["obesity_cond"]
    f["bmi_ge25"] = ((f["bmi_max"] is not None and f["bmi_max"] >= 25)
                     or f["overweight_cond"] or f["obesity_cond"])
    f["bmi_ge40"] = (f["bmi_max"] is not None and f["bmi_max"] >= 40) or f["severe_obesity"]
    return f


# ── rule registry:  recId -> callable(f) -> 1/0  ───────────────────────────────────────
# Every rec text is paraphrased in the comment; policy notes flagged.  All patients here
# are CCD-cohort by construction (they are in `patient ehr/`), so the CCD anchor is a gate,
# not a discriminator -- it never appears in a rule.

def R_universal(_):  # BASELINE: precondition is only CCD membership
    return 1


def _very_high_risk(f):
    """2023 CCD 'very high risk' ASCVD composite (drives LIPID:5/7/10):
       >=2 major ASCVD events, OR >=1 major event PLUS >=2 high-risk conditions.
    age>=65 and family history are NOT in the EHR dump, so they are omitted -- the
    composite is therefore a CONSERVATIVE lower bound (documented limitation)."""
    ascvd_events = sum([f["mi"], f["stroke"], f["pad"]])
    hi_risk = sum([f["dm"], f["htn"], f["ckd"], bool(f["smoker_recent"]),
                   f["hf"], (f["cabg"] or f["pci"])])
    return ascvd_events >= 2 or (ascvd_events >= 1 and hi_risk >= 2)


def R_bpm1(f):
    """BPM:1 -- elevated-BP category (120-129 / <80); most-recent BP; missing -> 0."""
    sbp, dbp = f["bp_recent"]
    return int(sbp is not None and 120 <= sbp <= 129 and (dbp is None or dbp < 80))


RULES = {
    # ---- universal / BASELINE (fire for every CCD patient) ----
    "LIPID:1": R_universal, "LIPID:3": R_universal,
    "NUTRI:1": R_universal, "NUTRI:2": R_universal, "NUTRI:3": R_universal, "NUTRI:4": R_universal,
    "TP:1": R_universal, "ASU:1": R_universal,
    "MHC:1": R_universal, "MHC:2": R_universal,
    "PA:1": R_universal, "PA:2": R_universal, "PA:3": R_universal,
    "SHA:1": R_universal, "SHA:2": R_universal, "WM:1": R_universal,
    "IMMU:1": R_universal, "IMMU:2": R_universal, "IMMU:3": R_universal,
    "EE:1": R_universal, "EE:2": R_universal, "COLC:1": R_universal,

    # ---- blood-pressure management (hypertension) ----
    "BPM:2": lambda f: int(f["htn"]),
    "BPM:3": lambda f: int(f["htn"]),

    # ---- diabetes / SGLT2 (SGLT2:4/6 are heart-failure-gated, irrespective of diabetes) ----
    "SGLT2:1": lambda f: int(f["dm"]),
    "SGLT2:4": lambda f: int(f["hf"] and f["lvef_min"] is not None and f["lvef_min"] <= 40),
    "SGLT2:6": lambda f: int(f["hf"] and f["lvef_min"] is not None and f["lvef_min"] > 40),

    # ---- lipids ----
    # LIPID:2  moderate-intensity statin WHEN high-intensity not tolerated -- proxy: on a
    #          statin that is NOT high-intensity.  No statin -> can't infer intolerance -> 0.
    #          (was mislabelled universal; review flagged it would mark no-statin pts as 1.)
    "LIPID:2": lambda f: int(f["statin"] and not f["high_statin"]),
    # LIPID:9  hypertriglyceridemia + LDL<100 + TG 150-499 -- BOTH labs must be present and
    #          in range (missing -> can't confirm -> 0, rule 3).
    "LIPID:9": lambda f: int(f["hypertg"]
                             and f["ldl_max"] is not None and f["ldl_max"] < 100
                             and f["tg_max"] is not None and 150 <= f["tg_max"] <= 499),
    # LIPID:5  VERY-HIGH-RISK + maximally-tolerated statin + LDL>=70 (add ezetimibe)
    "LIPID:5": lambda f: int(_very_high_risk(f) and f["statin"]
                             and (f["ldl_max"] is None or f["ldl_max"] >= 70)),
    # LIPID:7  VERY-HIGH-RISK + statin + ezetimibe already on board + LDL>=70 (PCSK9 tier)
    "LIPID:7": lambda f: int(_very_high_risk(f) and f["statin"] and f["ezetimibe"]
                             and (f["ldl_max"] is None or f["ldl_max"] >= 70)),
    # LIPID:10 NOT-very-high-risk + any-intensity statin + LDL>=70.  (LDL check present but
    #          LDL is unmeasured in this cohort -> defaults to pass.  Complementary to LIPID:5:
    #          the human split LIPID:5/10 on very-high-risk status.)
    "LIPID:10": lambda f: int(not _very_high_risk(f) and f["statin"]
                              and (f["ldl_max"] is None or f["ldl_max"] >= 70)),
    # LIPID:11 bempedoic/inclisiran AFTER ezetimibe+PCSK9 insufficient -> un-confirmable tier
    "LIPID:11": lambda f: POLICY_UNCONFIRMABLE,

    # ---- antiplatelet ----
    "APT:1": lambda f: int(not f["needs_oac"]),           # aspirin unless OAC indication
    "APT:2": lambda f: int(f["pci"]),                     # PCI-treated (procedure!)
    "APT:3": lambda f: POLICY_UNCONFIRMABLE,              # PCI+DES+completed-DAPT+P2Y12-mono: un-confirmable
    "APT:4": lambda f: POLICY_UNCONFIRMABLE,              # "low bleeding risk" score -> un-confirmable
    "APT:5": lambda f: int(f["mi"] and not f["stroke"]),  # prior MI, specified neg: no stroke/TIA/ICH
    "APT:6": lambda f: int(f["cabg"]),                    # after CABG
    "APT:11": lambda f: int(f["pci"] and f["needs_oac"]),
    "APT:12": lambda f: POLICY_UNCONFIRMABLE,             # "high thrombotic + low bleeding risk" score
    "APT:13": lambda f: POLICY_UNCONFIRMABLE,             # "low atherothrombotic risk" score
    "APT:14": lambda f: int(f["needs_oac"]),
    "APT:15": lambda f: POLICY_UNCONFIRMABLE,             # high ischemic / low bleeding risk score
    "APT:16": lambda f: int(f["dapt"]),                   # on DAPT -> PPI

    # ---- beta-blockers ----
    "BB:1": lambda f: int(f["lvef_min"] is not None and f["lvef_min"] <= 40),   # missing LVEF -> 0
    "BB:2": lambda f: int(f["lvef_min"] is not None and f["lvef_min"] < 50),
    # BB:4  no-benefit population = on BB, no MI, and LVEF confirmed >50.  Unknown LVEF ->
    #       can't confirm -> 0 (below, in SAFETY_RULES).
    # BB:3  reassess BB started for prior MI WITHOUT current LVEF<=50 / angina / arrhythmia /
    #       uncontrolled HTN (htn used as proxy for "uncontrolled"; requires being ON a BB)
    "BB:3": lambda f: int(f["beta_blocker"] and f["mi"]
                          and not (f["lvef_min"] is not None and f["lvef_min"] <= 50)
                          and not f["angina"] and not f["af"] and not f["htn"]),

    # ---- RAAS inhibitors ----
    "RAAI:1": lambda f: int(f["htn"] or f["dm"] or f["ckd"]
                            or (f["lvef_min"] is not None and f["lvef_min"] <= 40)),  # disjunctive
    "RAAI:2": lambda f: int(not (f["htn"] or f["dm"] or f["ckd"])
                            and f["lvef_min"] is not None and f["lvef_min"] > 40),

    # ---- cardiac rehab ----
    "CR:1:1": lambda f: int(f["mi"] or f["pci"] or f["cabg"]),   # after MI/PCI/CABG
    "CR:1:2": lambda f: int(f["angina"]),                        # stable angina / transplant (proxy)
    "CR:1:3": lambda f: int(f["scad"]),                          # after SCAD

    # ---- angina / antianginal ----
    "MTRA:1": lambda f: int(f["angina"]),
    "MTRA:2": lambda f: int(f["angina"]),
    "MTRA:3": lambda f: int(f["refractory_angina"]),   # "symptomatic despite" therapy = refractory
    "MTRA:4": lambda f: int(f["angina"]),              # rescue nitro for angina (angina-gated per kappa cross-check; matches MTRA:1/2)
    "MRA:1":  lambda f: int(f["refractory_angina"]),

    # ---- gated interventions (BP-range / alcohol / smoking-cessation / weight) ----
    "BPM:1": R_bpm1,                                    # elevated BP 120-129/<80 (most-recent)
    "ASU:2": lambda f: int(f["alcohol"]),              # consumes alcohol
    "TP:2":   lambda f: int(bool(f["smoker_recent"])),  # current (regular) smoker
    "TP:3:1": lambda f: int(bool(f["smoker_recent"])),
    "TP:3:2": lambda f: int(bool(f["smoker_recent"])),
    "TP:4":   lambda f: int(bool(f["smoker_recent"])),
    "TP:5":   lambda f: int(bool(f["smoker_recent"])),
    "WM:2":   lambda f: int(f["bmi_ge25"]),            # overweight or obesity
    "WM:3":   lambda f: int(f["bmi_ge25"]),            # overweight/obesity (pharmacotherapy = judgment)
    # WM:4 bariatric referral: severe obesity is confirmable, but the deciding
    # preconditions -- acceptable surgical risk, failed prior lifestyle+drug therapy --
    # are NOT, so per the strict labelling call this is always-0 (joins the risk-score recs).
    "WM:4":   lambda f: POLICY_UNCONFIRMABLE,
}

# ---- safety tier (cor 3 contraindications):  1 == the harmful/no-benefit situation holds ----
SAFETY_RULES = {
    # BB:4  no MI AND no LVEF<=50 -> beta-blocker not beneficial (fires only if ON a BB)
    "BB:4": lambda f: int(f["beta_blocker"] and not f["mi"]
                          and f["lvef_min"] is not None and f["lvef_min"] > 50),
    # SHA:3 PDE5i + nitrate concomitantly
    "SHA:3": lambda f: int(f["pde5i"] and f["nitrate"]),
    # APT:9 prasugrel + prior stroke/TIA/ICH
    "APT:9": lambda f: int(f["prasugrel"] and f["stroke"]),
    # APT:7 clopidogrel ADDED TO aspirin, without recent ACS or PCI indication (needs BOTH drugs)
    "APT:7": lambda f: int(f["clopidogrel"] and f["aspirin"] and not f["acs"] and not f["pci"]),
    # APT:10 CHRONIC NSAID -- chronicity from CSV course durations (cumulative >90d OR
    #        >=3 courses OR any single >30d); acute short courses excluded. See nsaid_csv.
    "APT:10": lambda f: int(f["nsaid_chronic"]),
}


# ── labelling ──────────────────────────────────────────────────────────────────────────
def patient_ids():
    """PIDs whose bundle contains the CCD gate code (bundle-based, non-circular) --
    the same 876 the CRS gate admits. Restrict with env PID_FILE (one uid per line)."""
    pid_file = os.environ.get("PID_FILE")
    if pid_file and os.path.exists(pid_file):
        return [ln.strip() for ln in open(pid_file, encoding="utf-8") if ln.strip()]
    pids = []
    for pid, path in BUNDLES.items():
        with open(path, encoding="utf-8", errors="replace") as f:
            if any(f'"{GATE_CODE}"' in line for line in f):
                pids.append(pid)
    return sorted(pids)


def label_patient(pid, include_safety=True):
    f = features(pid)
    out = {rec: fn(f) for rec, fn in RULES.items()}
    if include_safety:
        out.update({rec: fn(f) for rec, fn in SAFETY_RULES.items()})
    return f, out


def cmd_label(args):
    os.makedirs(EVAL_DIR, exist_ok=True)
    pids = [args.pid] if args.pid else patient_ids()
    rec_ids = list(RULES) + list(SAFETY_RULES)
    rows = []
    for pid in pids:
        f, labels = label_patient(pid)
        for rec in rec_ids:
            rows.append({"patientId": pid, "recId": rec, "oracle_label": labels[rec]})
        if args.pid:
            print(f"\n== features for {pid} ==")
            for k in ("htn", "dm", "mi", "cabg", "pci", "stroke", "ckd", "angina",
                      "dapt", "needs_oac", "lvef_min", "ldl_max", "bmi_max", "smoker_recent"):
                print(f"   {k:14} = {f[k]}")
            print(f"\n== labels for {pid} (1 = applicable) ==")
            for rec in rec_ids:
                print(f"   {rec:10} {labels[rec]}")
    if not args.pid:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["patientId", "recId", "oracle_label"])
            w.writeheader(); w.writerows(rows)
        print(f"-- wrote {len(rows)} labels for {len(pids)} patients -> {OUT_CSV}")
        pos = sum(r["oracle_label"] for r in rows)
        print(f"-- positive rate: {pos}/{len(rows)} = {pos/len(rows):.1%}")


# ── validation against manual gold ─────────────────────────────────────────────────────
def _load_manual():
    """Read eval/gold_labels.csv  (columns: patientId, recId, gold[/label/applicable])."""
    if not os.path.exists(MANUAL_LABELS):
        raise SystemExit(
            f"No {MANUAL_LABELS}. Provide a consolidated manual-label CSV with columns "
            "patientId, recId, gold (0/1) to validate against -- e.g. exported from your "
            "filled worksheets.")
    out = {}
    with open(MANUAL_LABELS, encoding="utf-8-sig") as fh:
        r = csv.DictReader(fh)
        cols = {c.lower(): c for c in r.fieldnames}
        pcol = cols.get("patientid") or cols.get("patient") or cols.get("pid")
        rcol = cols.get("recid") or cols.get("rec")
        gcol = (cols.get("gold") or cols.get("gold_label") or cols.get("label")
                or cols.get("applicable"))
        for row in r:
            rid = row[rcol].replace("CCD-2023:", "").strip()
            g = (row[gcol] or "").strip()
            if g in ("0", "1"):
                out[(row[pcol].strip(), rid)] = int(g)
    return out


def _kappa(a, b, c, d):
    # 2x2: a=both1, d=both0, b/c=disagree
    n = a + b + c + d
    if n == 0:
        return 0.0
    po = (a + d) / n
    p1 = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - p1) / (1 - p1) if p1 != 1 else 1.0


def cmd_validate(_):
    manual = _load_manual()
    if not manual:
        raise SystemExit("Manual label file had no usable 0/1 rows.")
    a = b = c = d = 0          # a=1/1 b=oracle1/gold0 c=oracle0/gold1 d=0/0
    disagreements = []
    for pid in patient_ids():
        _, labels = label_patient(pid)
        for rec, ol in labels.items():
            if (pid, rec) not in manual:
                continue
            gl = manual[(pid, rec)]
            if ol == 1 and gl == 1: a += 1
            elif ol == 1 and gl == 0: b += 1; disagreements.append((pid, rec, ol, gl))
            elif ol == 0 and gl == 1: c += 1; disagreements.append((pid, rec, ol, gl))
            else: d += 1
    n = a + b + c + d
    if n == 0:
        raise SystemExit("No overlapping (patient, rec) cells between oracle and manual labels.")
    # coverage gap: recs the human labelled but the oracle does not yet encode (excluded above)
    gap = sorted({rec for (_, rec) in manual} - (set(RULES) | set(SAFETY_RULES)))
    if gap:
        print(f"WARNING: {len(gap)} rec(s) in manual gold NOT encoded in the oracle "
              f"(not scored -- add rules for these): {gap}\n")
    print(f"compared {n} (patient x rec) cells")
    print(f"  agreement      : {(a+d)/n:.1%}  ({a+d}/{n})")
    print(f"  Cohen's kappa  : {_kappa(a, b, c, d):.3f}")
    print(f"  oracle=1 gold=0: {b}   (oracle over-labels)")
    print(f"  oracle=0 gold=1: {c}   (oracle under-labels)")
    print("\ndisagreements (drives rule tuning):")
    from collections import Counter
    for rec, k in Counter(r for _, r, _, _ in disagreements).most_common():
        print(f"  {rec:10} {k}")


# ── main ───────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("label", help="emit oracle labels for all patients (or --pid one)")
    pl.add_argument("--pid", help="label + print one patient verbosely")
    pl.set_defaults(func=cmd_label)
    pv = sub.add_parser("validate", help="compare oracle vs manual gold (agreement + kappa)")
    pv.set_defaults(func=cmd_validate)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
