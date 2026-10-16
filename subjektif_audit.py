# -*- coding: utf-8 -*-
r"""
subjektif_audit.py
==================
What subjective (patient-reported) information do the 30 sample patients' FHIR records hold?

Why this exists
---------------
Guideline logic for chronic coronary disease leans on symptoms: whether angina is present,
how often, how limiting, and how much exertion the patient tolerates. The rater guide already
warns that the synthetic records carry no meaningful complaint data, and Bab III needs to state
the same limitation. This script measures it rather than assuming it, over the 30 patients of
the gold-standard sample (eval/gold_labels.csv), reading only their raw FHIR bundles.

It reports:
  * clinical notes (DocumentReference) and their "Chief Complaint" lists -- how many distinct
    complaint lists each patient has across all visits, and which cardiac symptoms appear;
  * whether any note mentions a symptom grading or functional scale (CCS or NYHA class,
    angina frequency, exercise tolerance, METs, Seattle Angina Questionnaire);
  * patient-reported Observations that DO exist (pain score, depression / anxiety /
    substance-use questionnaires, social-needs surveys), so the limitation is not overstated;
  * coded angina diagnoses, which is how guideline logic here sees angina at all.

Usage:  python subjektif_audit.py [--write]      # --write -> eval/subjektif_audit.txt
"""
import base64
import csv
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
FHIR = os.path.join(BASE, "sihd+general", "fhir")
GOLD = os.path.join(BASE, "eval", "gold_labels.csv")
REPORT = os.path.join(BASE, "eval", "subjektif_audit.txt")

CARDIAC = ("chest pain", "chest pressure", "chest tightness", "angina", "dyspnea",
           "shortness of breath", "breathless", "palpitation", "syncope", "orthopnea",
           "edema", "swelling", "exercise intolerance", "exertional")
SCALES = re.compile(r"\b(CCS|NYHA|Canadian Cardiovascular|New York Heart|class [IV]+\b|"
                    r"angina (?:frequency|class)|exercise tolerance|functional capacity|"
                    r"METs?\b|Seattle Angina)", re.I)
# patient-reported instruments Synthea emits as Observations (LOINC, display fragment)
PRO = {"72514-3": "pain severity 0-10", "55758-7": "PHQ-2", "44261-6": "PHQ-9",
       "69737-5": "GAD-7", "70274-6": "GAD-7 total", "82667-7": "DAST-10",
       "72109-2": "AUDIT-C", "75626-2": "AUDIT-C total", "93025-5": "PRAPARE",
       "76504-0": "HARK", "89204-2": "patient health questionnaire"}


def cohort():
    with io.open(GOLD, encoding="utf-8-sig", newline="") as f:
        return sorted({r["patientId"] for r in csv.DictReader(f)})


def bundle(pid):
    return json.load(io.open(glob.glob(os.path.join(FHIR, "*_%s.json" % pid))[0], encoding="utf-8"))


def chief_complaint(note):
    m = re.search(r"# Chief Complaint\s*\n(.*?)(?:\n\s*\n#|\n#)", note, re.S)
    if not m:
        return None
    items = [l.strip("- ").strip().lower() for l in m.group(1).splitlines() if l.strip().startswith("-")]
    body = m.group(1).strip().lower()
    return tuple(sorted(items)) if items else ((body,) if body else ())


def main(write=False):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    pids = cohort()
    n_notes = 0
    lists_per_pat = {}
    varying = 0
    cardiac_hits = Counter()
    pats_with_cardiac = set()
    scale_hits = Counter()
    pro = Counter()
    pro_pats = defaultdict(set)
    angina_pats = Counter()
    pats_with_angina_code = set()
    empty_cc = 0

    for pid in pids:
        d = bundle(pid)
        seen_lists = set()
        for e in d["entry"]:
            r = e["resource"]
            rt = r["resourceType"]
            if rt == "DocumentReference":
                for c in r.get("content", []):
                    data = c.get("attachment", {}).get("data")
                    if not data:
                        continue
                    note = base64.b64decode(data).decode("utf-8", "replace")
                    n_notes += 1
                    cc = chief_complaint(note)
                    if cc is None or cc == () or cc == ("no complaints.",):
                        empty_cc += 1
                    else:
                        seen_lists.add(cc)
                        for item in cc:
                            for k in CARDIAC:
                                if k in item:
                                    cardiac_hits[item] += 1
                                    pats_with_cardiac.add(pid)
                    for m in SCALES.finditer(note):
                        scale_hits[m.group(0)] += 1
            elif rt == "Observation":
                for cd in r.get("code", {}).get("coding", []):
                    if cd.get("code") in PRO:
                        pro[PRO[cd["code"]]] += 1
                        pro_pats[PRO[cd["code"]]].add(pid)
            elif rt == "Condition":
                for cd in r.get("code", {}).get("coding", []):
                    disp = (cd.get("display") or "").lower()
                    if "angina" in disp:
                        angina_pats[cd.get("display")] += 1
                        pats_with_angina_code.add(pid)
        lists_per_pat[pid] = len(seen_lists)
        if len(seen_lists) > 1:
            varying += 1

    out("=" * 78)
    out("SUBJECTIVE DATA IN THE %d SAMPLE PATIENTS' FHIR RECORDS" % len(pids))
    out("=" * 78)
    out("")
    out("-- 1. clinical notes ---------------------------------------------------------")
    out("notes (DocumentReference)                : %d" % n_notes)
    out("notes with no chief complaint            : %d" % empty_cc)
    dist = Counter(lists_per_pat.values())
    out("distinct chief-complaint lists per patient, across all visits:")
    for k in sorted(dist):
        out("   %d list(s): %d patient(s)" % (k, dist[k]))
    out("patients whose complaint list ever changes : %d of %d" % (varying, len(pids)))
    out("")
    out("-- 2. cardiac symptoms in chief complaints ----------------------------------")
    out("patients with any cardiac symptom listed : %d of %d" % (len(pats_with_cardiac), len(pids)))
    for k, v in cardiac_hits.most_common():
        out("   %-40s %d note(s)" % (k, v))
    out("")
    out("-- 3. symptom grading or functional scales in note text --------------------")
    if scale_hits:
        for k, v in scale_hits.most_common():
            out("   %-40s %d" % (k, v))
    else:
        out("   none: no CCS or NYHA class, angina frequency, exercise tolerance, METs,")
        out("   or Seattle Angina Questionnaire anywhere in %d notes" % n_notes)
    out("")
    out("-- 4. patient-reported observations that do exist --------------------------")
    for k, v in pro.most_common():
        out("   %-28s %5d observation(s), %2d patient(s)" % (k, v, len(pro_pats[k])))
    out("")
    out("-- 5. how angina reaches the guideline logic: coded diagnoses --------------")
    out("patients with any angina diagnosis code  : %d of %d" % (len(pats_with_angina_code), len(pids)))
    for k, v in angina_pats.most_common():
        out("   %-40s %d" % (k, v))

    if write:
        with io.open(REPORT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("\nwritten: %s" % os.path.relpath(REPORT, BASE))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
