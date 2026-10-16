r"""
build_gold_labels.py
====================
Consolidate the filled manual worksheets into one eval/gold_labels.csv
(columns: patientId, recId, gold) for `silver_oracle.py validate`.

READS (never modifies) the user's filled worksheets:
  eval/worksheet_<pid>.csv   -- 68 positive recs.  Label col = gold_applicable.
                                patientId comes from the FILENAME, one row per rec.
  eval/safety_worksheet.csv  -- 13 safety recs.     Label col = gold_true_contra.
                                patientId is a COLUMN; there are MULTIPLE rows per
                                (patient, rec) -- one per drug -- so they are aggregated
                                with MAX (contraindication applies if ANY drug row = 1).

WRITES:  eval/gold_labels.csv   (recId stored WITHOUT the "CCD-2023:" prefix)

Runs in .venv (stdlib only).
Usage:
    .\.venv\Scripts\python.exe build_gold_labels.py
"""
import os
import csv
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(BASE, "eval")
OUT = os.path.join(EVAL, "gold_labels.csv")

POS_LABEL_COLS = ("gold_applicable", "gold", "label", "applicable")
SAFE_LABEL_COLS = ("gold_true_contra", "gold", "label")


def _read(path):
    """Excel re-saves these as cp1252; fall back utf-8-sig -> cp1252 -> latin-1."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    with open(path, encoding="latin-1", errors="replace") as f:
        return list(csv.DictReader(f))


def _pick(fieldnames, candidates):
    low = {c.lower().strip(): c for c in fieldnames}
    for c in candidates:
        if c in low:
            return low[c]
    return None


def _binlabel(raw):
    """Parse a 0/1 label tolerating '1', '1.0', ' 0 ' etc.  Returns 0/1 or None."""
    try:
        v = int(float((raw or "").strip()))
    except (ValueError, TypeError):
        return None
    return v if v in (0, 1) else None


def _strip_rec(rid):
    return (rid or "").replace("CCD-2023:", "").strip()


def main():
    labels = {}                      # (pid, recId) -> 0/1
    n_pos = n_safe = 0

    # ── positive worksheets (patientId from filename) ──
    for path in sorted(glob.glob(os.path.join(EVAL, "worksheet_*.csv"))):
        pid = os.path.basename(path)[len("worksheet_"):-len(".csv")]
        rows = _read(path)
        if not rows:
            continue
        rcol = _pick(rows[0].keys(), ("recid",))
        gcol = _pick(rows[0].keys(), POS_LABEL_COLS)
        if not rcol or not gcol:
            print(f"  !! skipped {os.path.basename(path)} (missing recId/gold_applicable)")
            continue
        for r in rows:
            g = _binlabel(r.get(gcol))
            if g is not None:
                labels[(pid, _strip_rec(r[rcol]))] = g
                n_pos += 1

    # ── safety worksheet (patientId column; aggregate MAX over drug rows) ──
    spath = os.path.join(EVAL, "safety_worksheet.csv")
    if os.path.exists(spath):
        rows = _read(spath)
        if rows:
            pcol = _pick(rows[0].keys(), ("patientid", "patient", "pid"))
            rcol = _pick(rows[0].keys(), ("recid",))
            gcol = _pick(rows[0].keys(), SAFE_LABEL_COLS)
            if pcol and rcol and gcol:
                for r in rows:
                    g = _binlabel(r.get(gcol))
                    if g is None:
                        continue
                    key = (r[pcol].strip(), _strip_rec(r[rcol]))
                    labels[key] = max(labels.get(key, 0), g)   # any drug row 1 -> 1
                    n_safe += 1
            else:
                print("  !! safety_worksheet.csv missing patientId/recId/gold_true_contra")

    os.makedirs(EVAL, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["patientId", "recId", "gold"])
        for (pid, rid), g in sorted(labels.items()):
            w.writerow([pid, rid, g])

    pats = len({p for p, _ in labels})
    pos = sum(labels.values())
    print(f"-- positive worksheet rows read : {n_pos}")
    print(f"-- safety worksheet rows read   : {n_safe} (pre-aggregation)")
    print(f"-- wrote {len(labels)} (patient x rec) labels for {pats} patients -> {OUT}")
    if labels:
        print(f"-- positive-label rate          : {pos}/{len(labels)} = {pos/len(labels):.1%}")


if __name__ == "__main__":
    main()
