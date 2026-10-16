r"""
pick_review_patients.py
=======================
Rank the cohort for suitability as EXAMPLE CASES in the clinical (cardiologist)
validation packet.

Why this exists: the patients are Synthea-generated, so some records carry artifacts a
cardiologist would (rightly) object to -- most notably **non-physiological LVEF** values.
If you hand those over, the expert ends up critiquing Synthea rather than your system, and
the review is unfair to the work. This screens them out and favours cases that actually
exercise the briefing:

  PLAUSIBILITY (screen out artifacts)
    - LVEF present but outside 20-70%  -> non-physiological, penalise hard
    - very sprawling / very thin condition lists -> mild penalty

  REVIEW VALUE (make the briefing worth reading)
    - discriminating comorbidities (MI/CABG/PCI/DM/HTN/CKD/HF/stroke/hyperTG)
      -> drives PATIENT-SPECIFIC recommendations (the interesting tier)
    - safety-relevant drugs (beta-blocker/nitrate/NSAID/P2Y12/prasugrel/PDE5i)
      -> a non-empty SAFETY FLAGS section

Reads the RAW record only (via silver_oracle's extractors) -- no Neo4j needed.

Runs in .venv (stdlib + silver_oracle).
Usage:
    .\.venv\Scripts\python.exe pick_review_patients.py
    .\.venv\Scripts\python.exe pick_review_patients.py --top 3
"""

import sys
import argparse

import silver_oracle as go

DISCRIMINATORS = ("mi", "cabg", "pci", "dm", "htn", "ckd", "hf", "stroke", "hypertg")
SAFETY_DRUGS = ("beta_blocker", "nitrate", "nsaid", "p2y12", "prasugrel", "pde5i")


def assess(pid):
    f = go.features(pid)
    ehr = go.load_ehr(pid)
    n_cond = len(set(ehr["cond"]))

    flags = []
    score = 0

    # ── plausibility screen ──
    lvef = f["lvef_min"]
    if lvef is not None and not (20 <= lvef <= 70):
        flags.append(f"LVEF {lvef} non-physiological")
        score -= 10
    if n_cond > 70:
        flags.append(f"{n_cond} conditions (sprawling)")
        score -= 3
    elif n_cond < 15:
        flags.append(f"only {n_cond} conditions (thin)")
        score -= 2

    # ── review value ──
    n_disc = sum(1 for k in DISCRIMINATORS if f[k])
    n_safe = sum(1 for k in SAFETY_DRUGS if f[k])
    score += min(n_disc, 6) * 2
    score += min(n_safe, 3)
    if n_safe == 0:
        flags.append("no safety-flag drug (empty safety section)")

    return {
        "pid": pid, "score": score, "n_disc": n_disc, "n_safe": n_safe,
        "n_cond": n_cond, "lvef": lvef, "flags": flags,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=5, help="how many to recommend (default 5)")
    args = ap.parse_args()

    rows = sorted((assess(p) for p in go.patient_ids()),
                  key=lambda r: (-r["score"], r["pid"]))

    print(f"{'patient':<12}{'score':>6}{'discrim':>8}{'safety':>7}{'conds':>6}{'LVEF':>7}  flags")
    for r in rows:
        lv = "-" if r["lvef"] is None else f"{r['lvef']:.1f}"
        print(f"{r['pid'][:12]:<12}{r['score']:>6}{r['n_disc']:>8}{r['n_safe']:>7}"
              f"{r['n_cond']:>6}{lv:>7}  {'; '.join(r['flags'])}")

    clean = [r for r in rows if not any("non-physiological" in x for x in r["flags"])]
    print("\n" + "=" * 78)
    print(f"RECOMMENDED for the cardiologist packet (top {args.top}, artifact-free):")
    for r in clean[:args.top]:
        print(f"  {r['pid']}   score={r['score']}  "
              f"{r['n_disc']} discriminating comorbidities, {r['n_safe']} safety drug(s)")
    n_bad = len(rows) - len(clean)
    if n_bad:
        print(f"\n  ({n_bad} patient(s) screened out for non-physiological LVEF -- "
              "excluding them keeps the review about the SYSTEM, not Synthea.)")
    print("\nGenerate each briefing with:")
    print("  .\\.venv\\Scripts\\python.exe crs_briefing.py <patientId> --save")


if __name__ == "__main__":
    main()
