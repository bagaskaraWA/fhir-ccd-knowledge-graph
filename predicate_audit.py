# -*- coding: utf-8 -*-
r"""
predicate_audit.py
==================
Audit where the reference standard shares a predicate with the system under test, and
report the concordance with those recommendations removed.

Why this exists
---------------
silver_oracle.py calls itself "CRS-INDEPENDENT", and the thesis reports concordance against
it as though every recommendation were checked by an independent judge. For most
recommendations that holds. For the 15 observation-gated ones it does not, and the examiner
asked how much of the headline rests on the part that does not.

The situation is narrower than "circular" and wider than "independent":

  * The 53 non-gated recommendations are decided by the graph's gate+AND traversal over
    UMLS-bridged codes. The oracle decides them by substring matching over condition
    displays read from the raw bundle. Different logic, different data path -- and they
    disagree substantially, which is what makes precision and recall informative there.

  * The 15 observation-gated recommendations are decided by a Python predicate in
    obs_gate.OBS_GATE that was copied verbatim from silver_oracle.RULES. Same logic. The
    two sides still read the patient's values from different places -- the gate from the
    graph's Observation nodes, the oracle from the raw FHIR bundle -- so agreement there
    is evidence about the DATA PATH (the loader carries values unchanged) and not about
    the clinical rule. The rule cannot be wrong on one side and right on the other,
    because it is the same rule.

This script establishes both halves as fact rather than as description. Section 2 proves
the 15 predicates are the same FUNCTION, not merely similar source, by evaluating both on
the real cohort and on synthetic feature vectors drawn to straddle every threshold.
Section 3 recomputes the concordance with the shared-predicate recommendations removed, so
the reader can see what the independent part alone supports.

Usage:
    python predicate_audit.py             # print the audit
    python predicate_audit.py --write     # also write eval/predicate_audit.txt
"""

import io
import os
import sys
import random
import itertools

import obs_gate
import silver_oracle

BASE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.join(BASE, "eval")
CONCORDANCE = os.path.join(EVAL_DIR, "concordance_by_class.txt")
COHORT_FILE = os.path.join(EVAL_DIR, "gate_cohort_pids.txt")
REPORT = os.path.join(EVAL_DIR, "predicate_audit.txt")

TRIALS = 200000
SEED = 20260921

# The classes eval_by_class.py assigns. value-gated and both are exactly OBS_GATED; see
# eval_by_class.classify(), which sets them from membership in obs_gate.OBS_GATED.
SHARED_CLASSES = ("value-gated", "both")

# Boundaries every gated predicate tests, used to aim the synthetic draws.
BOUNDS = {"lvef_min": (40.0, 50.0), "bmi_max": (25.0, 40.0), "ldl_max": (100.0,),
          "tg_max": (150.0, 499.0), "sbp": (120.0, 129.0), "dbp": (80.0,)}
BOOLS = ("hf", "htn", "dm", "ckd", "hypertg", "smoker_recent",
         "obesity_cond", "overweight_cond", "severe_obesity")


def short(rec):
    return rec.split("CCD-2023:", 1)[-1]


# ── section 2: are the 15 predicates the same function? ───────────────────────────────

def derive(f):
    """Apply the derived-feature formulas both sides expect, identically."""
    f["bmi_ge25"] = ((f["bmi_max"] is not None and f["bmi_max"] >= 25)
                     or f["overweight_cond"] or f["obesity_cond"])
    f["bmi_ge40"] = (f["bmi_max"] is not None and f["bmi_max"] >= 40) or f["severe_obesity"]
    # The one plumbing difference: the oracle reads f["bp_recent"], the gate reads
    # f["sbp"] / f["dbp"]. Held consistent on purpose -- this test is about the logic.
    f["bp_recent"] = (f["sbp"], f["dbp"])
    return f


def draw(rng):
    """One synthetic feature vector, weighted onto the threshold boundaries."""
    f = {}
    for k, bounds in BOUNDS.items():
        r = rng.random()
        if r < 0.15:
            f[k] = None
        elif r < 0.75:
            b = rng.choice(bounds)
            f[k] = b + rng.choice((-0.1, -0.01, 0.0, 0.01, 0.1))
        else:
            f[k] = rng.uniform(0.0, 600.0)
    for k in BOOLS:
        f[k] = rng.random() < 0.5
    return derive(f)


def real_vectors():
    """The 876 cohort feature vectors, from the raw bundles."""
    with io.open(COHORT_FILE, encoding="utf-8") as fh:
        pids = [l.strip() for l in fh if l.strip()]
    out = []
    for pid in pids:
        g = silver_oracle.features(pid)
        f = {k: g[k] for k in BOUNDS if k in g}
        f["sbp"], f["dbp"] = g["bp_recent"]
        for k in BOOLS:
            f[k] = g[k]
        out.append(derive(f))
    return out


def equivalence(vectors, label, out):
    """Evaluate gate predicate and oracle rule on the same vectors; report disagreement."""
    rows = []
    total_disagree = 0
    for rec in sorted(obs_gate.OBS_GATED):
        s = short(rec)
        gate = obs_gate.OBS_GATE[rec]
        rule = silver_oracle.RULES[s]
        n = 0
        for f in vectors:
            if bool(gate(f)) != bool(rule(f)):
                n += 1
        total_disagree += n
        rows.append((s, n))
    out("%-12s %s vectors" % (label, len(vectors)))
    bad = [r for r in rows if r[1]]
    if bad:
        for s, n in bad:
            out("    DIFFERS  %-10s %d" % (s, n))
    else:
        out("    all 15 predicates agree on every vector")
    return total_disagree


# ── section 3: concordance with the shared-predicate recommendations removed ───────────

def parse_arm1():
    """Micro-averaged per-class counts from ARM 1 of eval/concordance_by_class.txt."""
    text = io.open(CONCORDANCE, encoding="utf-8").read()
    i = text.find("ARM 1")
    j = text.find("CONCORDANCE BY DISCRIMINATION CLASS", i)
    k = text.find("macro-averaged", j)
    rows = {}
    for line in text[j:k].splitlines():
        parts = line.split()
        if len(parts) == 8 and parts[0] in ("universal", "concept-matched",
                                            "value-gated", "both", "ALL"):
            rows[parts[0]] = dict(recs=int(parts[1]), tp=int(parts[5]),
                                  fp=int(parts[6]), fn=int(parts[7]))
    return rows


def prf(tp, fp, fn):
    p = tp / float(tp + fp) if tp + fp else 0.0
    r = tp / float(tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main(write=False):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    out("=" * 78)
    out("PREDICATE AUDIT -- where the reference standard shares logic with the system")
    out("=" * 78)
    out("")

    # --- 1. inventory -----------------------------------------------------------------
    out("-- 1. how each recommendation is decided on each side ----------------------")
    gated = {short(r) for r in obs_gate.OBS_GATED}
    allrecs = set(silver_oracle.RULES)
    out("recommendations scored                      : %d" % len(allrecs))
    out("  decided by graph traversal (independent)  : %d" % len(allrecs - gated))
    out("  decided by a predicate copied from the")
    out("  reference standard (shared logic)         : %d" % len(gated))
    out("")
    out("shared-predicate recommendations:")
    out("  " + ", ".join(sorted(gated)))
    out("")
    missing = gated - allrecs
    out("every shared predicate has a matching rule in silver_oracle.RULES : %s"
        % (not missing))
    if missing:
        out("  MISSING: %s" % sorted(missing))
    out("")

    # --- 2. same function, not merely similar source ----------------------------------
    out("-- 2. are those 15 predicates the same function? ---------------------------")
    out("Source inspection shows the gate predicates copied verbatim from the oracle's")
    out("rules. Copied text is weaker evidence than identical behaviour, so both are")
    out("evaluated on the same feature vectors and compared.")
    out("")
    d1 = equivalence(real_vectors(), "real cohort:", out)
    rng = random.Random(SEED)
    d2 = equivalence([draw(rng) for _ in range(TRIALS)], "synthetic:", out)
    out("")
    out("Synthetic vectors are drawn onto the boundaries every predicate tests (%s),"
        % ", ".join(sorted(BOUNDS)))
    out("including missing values, so a difference in threshold or in comparison")
    out("direction would surface. Total disagreements: %d." % (d1 + d2))
    out("")
    if d1 + d2 == 0:
        out("The gate predicate and the reference rule are therefore the SAME FUNCTION for")
        out("these 15 recommendations. Their agreement in the evaluation cannot be evidence")
        out("that the rule is clinically right; it is evidence that the two data paths")
        out("deliver the same values to it.")
    else:
        out("They are NOT the same function -- the claim in this docstring needs revising.")
    out("")

    # --- 3. what the headline rests on -------------------------------------------------
    out("-- 3. concordance with the shared-predicate recommendations removed --------")
    rows = parse_arm1()
    shared = [rows[c] for c in SHARED_CLASSES if c in rows]
    all_ = rows["ALL"]
    s_tp = sum(r["tp"] for r in shared)
    s_fp = sum(r["fp"] for r in shared)
    s_fn = sum(r["fn"] for r in shared)
    i_tp, i_fp, i_fn = all_["tp"] - s_tp, all_["fp"] - s_fp, all_["fn"] - s_fn

    out("%-28s %7s %7s %7s %9s %7s %6s" % ("subset", "P", "R", "F1", "tp", "fp", "fn"))
    for label, (tp, fp, fn), n in (
            ("headline (all %d)" % all_["recs"], (all_["tp"], all_["fp"], all_["fn"]), all_["recs"]),
            ("shared predicate (%d)" % sum(r["recs"] for r in shared), (s_tp, s_fp, s_fn), 0),
            ("independent logic (%d)" % (all_["recs"] - sum(r["recs"] for r in shared)),
             (i_tp, i_fp, i_fn), 0)):
        p, r, f = prf(tp, fp, fn)
        out("%-28s %7.3f %7.3f %7.3f %9d %7d %6d" % (label, p, r, f, tp, fp, fn))
    out("")
    hp, hr, hf = prf(all_["tp"], all_["fp"], all_["fn"])
    ip, ir, if_ = prf(i_tp, i_fp, i_fn)
    out("removing them moves precision by %+.3f and F1 by %+.3f" % (ip - hp, if_ - hf))
    out("share of the headline's true positives that are shared-predicate : %.1f%%"
        % (100.0 * s_tp / all_["tp"]))
    out("")
    out("The observation-gate ablation is affected differently. Only value-gated and both")
    out("change between the ablation arms (eval_by_class.py), and those are exactly the")
    out("shared-predicate recommendations -- so the whole of the reported ablation gain is")
    out("measured on them. That gain is still a real change in the system's behaviour, but")
    out("the reference standard it is measured against is not an independent judge of the")
    out("rule being applied; it is an independent judge of the values fed to it.")
    out("")

    if write:
        with io.open(REPORT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("written: %s" % os.path.relpath(REPORT, BASE))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
