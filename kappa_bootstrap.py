# -*- coding: utf-8 -*-
r"""
kappa_bootstrap.py
==================
How much should kappa = 0.991 be trusted, given that it comes from 30 patients?

Why this exists
---------------
The examiner asked whether 30 patients labelled by one annotator are enough to validate
the silver standard and its kappa = 0.991. A point estimate alone cannot answer that. This
script puts an interval on it.

The 2,160 compared cells are not independent: they come in 30 clusters, one per patient,
and a patient's record drives all ~72 of its labels at once. Resampling CELLS would treat
the sample as 2,160 independent observations and give an interval that is too narrow.
Resampling PATIENTS -- the cluster bootstrap -- keeps each patient's cells together and
answers the question actually asked: how different could kappa have been with a different
30 patients? Both are reported, so the size of the difference is visible.

It also reports:
  * prevalence and bias indices, and PABAK, to show kappa is not inflated or deflated by
    skewed label prevalence (the "kappa paradox");
  * a leave-one-patient-out jackknife, to show how much any single patient moves kappa;
  * how the 10 disagreements are spread over patients, which is what drives the interval.

What it cannot address is the single annotator: resampling cannot create a second rater.

Inputs:  eval/gold_labels.csv, eval/silver_oracle_labels.csv   (stdlib only)
Usage:   python kappa_bootstrap.py [--write]     # --write -> eval/kappa_bootstrap.txt
"""
import csv
import io
import math
import os
import random
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(BASE, "eval", "gold_labels.csv")
SILVER = os.path.join(BASE, "eval", "silver_oracle_labels.csv")
REPORT = os.path.join(BASE, "eval", "kappa_bootstrap.txt")

B = 10000
SEED = 20260927
THRESHOLDS = (0.80, 0.90, 0.95)


def load():
    """patient -> list of (silver, gold) pairs, over the cells both standards label."""
    silver = {}
    with io.open(SILVER, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            silver[(r["patientId"], r["recId"])] = int(r["oracle_label"])
    by_pat = defaultdict(list)
    with io.open(GOLD, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            k = (r["patientId"], r["recId"])
            if k in silver and r["gold"] in ("0", "1"):
                by_pat[r["patientId"]].append((silver[k], int(r["gold"])))
    return dict(by_pat)


def table(pairs):
    """2x2 counts: a = both 1, b = silver 1 / gold 0, c = silver 0 / gold 1, d = both 0."""
    a = b = c = d = 0
    for s, g in pairs:
        if s and g:
            a += 1
        elif s and not g:
            b += 1
        elif g and not s:
            c += 1
        else:
            d += 1
    return a, b, c, d


def kappa(a, b, c, d):
    n = a + b + c + d
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def kappa_of(counts):
    return kappa(*counts)


def add(t1, t2):
    return tuple(x + y for x, y in zip(t1, t2))


def pct(xs, q):
    """Percentile by linear interpolation on sorted data."""
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[f] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)


def var(xs):
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def main(write=False):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    by_pat = load()
    pats = sorted(by_pat)
    per_table = {p: table(by_pat[p]) for p in pats}
    tot = (0, 0, 0, 0)
    for p in pats:
        tot = add(tot, per_table[p])
    a, b, c, d = tot
    n = a + b + c + d
    k_hat = kappa(*tot)

    out("=" * 78)
    out("KAPPA WITH UNCERTAINTY -- silver standard vs manual gold, %d patients" % len(pats))
    out("=" * 78)
    out("")
    out("-- 1. point estimate -----------------------------------------------------")
    out("cells compared            : %d   (both 1: %d, both 0: %d, silver 1/gold 0: %d, "
        "silver 0/gold 1: %d)" % (n, a, d, b, c))
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    out("observed agreement p_o    : %.4f   (%d/%d)" % (po, a + d, n))
    out("chance agreement p_e      : %.4f" % pe)
    out("Cohen's kappa             : %.4f" % k_hat)
    out("")

    out("-- 2. is kappa distorted by label prevalence? -----------------------------")
    prev_gold = (a + c) / n
    prev_silver = (a + b) / n
    out("positive labels, gold     : %d/%d = %.3f" % (a + c, n, prev_gold))
    out("positive labels, silver   : %d/%d = %.3f" % (a + b, n, prev_silver))
    out("prevalence index |a-d|/n  : %.4f" % (abs(a - d) / n))
    out("bias index |b-c|/n        : %.4f" % (abs(b - c) / n))
    out("PABAK = 2*p_o - 1         : %.4f" % (2 * po - 1))
    out("Labels are almost exactly balanced and the disagreements symmetric, so chance")
    out("agreement sits near 0.5, kappa and PABAK coincide, and neither prevalence nor")
    out("bias is inflating or deflating kappa.")
    out("")

    out("-- 3. where the disagreements are ---------------------------------------")
    dis = {p: per_table[p][1] + per_table[p][2] for p in pats}
    carriers = [p for p in pats if dis[p]]
    out("disagreements             : %d, on %d of %d patients" % (b + c, len(carriers), len(pats)))
    for p in carriers:
        out("   %s  %d" % (p[:8], dis[p]))
    p_clean = (1 - len(carriers) / len(pats)) ** len(pats)
    out("chance a resample of %d patients contains none of them: %.1e" % (len(pats), p_clean))
    out("")

    rng = random.Random(SEED)

    # cell-level (naive): treats the 2,160 cells as independent draws
    cells = [pair for p in pats for pair in by_pat[p]]
    naive = []
    for _ in range(B):
        t = table(rng.choice(cells) for _ in range(len(cells)))
        naive.append(kappa_of(t))

    # patient-level (cluster): resample whole patients
    clus = []
    for _ in range(B):
        t = (0, 0, 0, 0)
        for _ in range(len(pats)):
            t = add(t, per_table[rng.choice(pats)])
        clus.append(kappa_of(t))

    out("-- 4. 95%% intervals, %d bootstrap replicates each ---------------------" % B)
    out("%-34s %8s %8s %8s" % ("resampling unit", "2.5%", "97.5%", "width"))
    for label, xs in (("cells (assumes independence)", naive), ("patients (cluster bootstrap)", clus)):
        lo, hi = pct(xs, 0.025), pct(xs, 0.975)
        out("%-34s %8.4f %8.4f %8.4f" % (label, lo, hi, hi - lo))
    deff = var(clus) / var(naive)
    out("design effect (var patients / var cells): %.2f" % deff)
    out("")
    out("share of cluster-bootstrap replicates with kappa >= threshold:")
    for th in THRESHOLDS:
        out("   >= %.2f : %.4f" % (th, sum(k >= th for k in clus) / B))
    out("")

    out("-- 5. leave-one-patient-out jackknife --------------------------------------")
    loo = []
    for p in pats:
        t = (0, 0, 0, 0)
        for q in pats:
            if q != p:
                t = add(t, per_table[q])
        loo.append((kappa_of(t), p))
    loo.sort()
    out("kappa without one patient ranges from %.4f (dropping %s) to %.4f (dropping %s)"
        % (loo[0][0], loo[0][1][:8], loo[-1][0], loo[-1][1][:8]))
    out("")

    lo = pct(clus, 0.025)
    out("-- 6. reading -----------------------------------------------------------------")
    out("With patients as the resampling unit, the 95%% interval is %.3f to %.3f." % (lo, pct(clus, 0.975)))
    out("Its lower end is %s the conventional 0.80 threshold for almost perfect agreement,"
        % ("above" if lo > 0.80 else "BELOW"))
    out("so 30 patients %s to support the claim that the silver standard agrees almost"
        % ("are enough" if lo > 0.80 else "are NOT enough"))
    out("perfectly with the manual labels. They are not enough to distinguish 0.99 from,")
    out("say, 0.98: that finer claim is not supported and should not be made.")
    out("None of this addresses the single annotator; that remains a limitation.")

    if write:
        with io.open(REPORT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("\nwritten: %s" % os.path.relpath(REPORT, BASE))
    return 0


if __name__ == "__main__":
    sys.exit(main(write="--write" in sys.argv))
