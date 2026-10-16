r"""
nsaid_csv.py
============
NSAID chronicity from Synthea's **CSV** medication export -- the source for APT:10
gold labelling.

The FHIR bundle/graph drops the medication STOP date (MedicationRequest carries only
`authoredOn`), so the full operational rule can only be computed from the CSV, which
keeps `START` / `STOP` / `DISPENSES` per medication episode. This module reads the CSV
directly; it is deliberately independent of Neo4j and of the FHIR bundle readers.

Operational rule (documented, applied uniformly to every patient):

    chronic = an OPEN-ENDED (ongoing, no-STOP) course
              OR cumulative NSAID exposure > 90 days
              OR >= 3 separate courses
              OR any single course         > 30 days
    otherwise acute (0).

One `medications.csv` row = one course (`START`..`STOP`). A row without a `STOP`
(~10% of NSAID rows) is an open-ended / still-active prescription -> treated as chronic
on its own (the `ongoing` arm): an un-discontinued NSAID is ongoing use. It contributes
no measured duration to the cumulative / single-course arms (its end is unknown), but
the ongoing arm covers it -- added after the manual kappa cross-check flagged 3 lone-
ongoing-naproxen patients the human correctly labelled chronic. The CSV `PATIENT` column
IS the FHIR patient `uid`; rows are unioned across BOTH runs (csv_sihd + csv_general).

NB the FHIR graph has no stop DATE, but it does have a categorical MedicationRequest
`status` (active/completed) that maps 1:1 to the CSV STOP (active == empty STOP ==
ongoing). So the graph reproduces TWO of the four arms -- `>= 3 courses OR ongoing
(status='active')` -- via chronicity_graph() below; only the two duration arms
(cumulative, single-course) genuinely need this CSV. The remaining APT:10 gap between
chronicity_graph (graph) and chronicity (CSV) is the honest FHIR limitation.
"""
import csv
import datetime as _dt
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_FILES = [
    os.path.join(BASE, "sihd+general", "csv_sihd", "medications.csv"),
    os.path.join(BASE, "sihd+general", "csv_general", "medications.csv"),
]

# Keep in sync with silver_oracle.NSAIDS.
NSAIDS = ("ibuprofen", "naproxen", "celecoxib", "diclofenac", "meloxicam",
          "indomethacin", "ketorolac", "piroxicam")

CUMULATIVE_DAYS = 90      # chronic if total exposure  >  90 d
COURSES = 3              # chronic if separate courses >= 3
SINGLE_COURSE_DAYS = 30  # chronic if any one course  >  30 d

# medications.csv columns: START,STOP,PATIENT,PAYER,ENCOUNTER,CODE,DESCRIPTION,...
_START, _STOP, _PATIENT, _DESC = 0, 1, 2, 6

_INDEX = None


def _date(s):
    """Date part of a Synthea ISO-8601 stamp (trailing Z / offset ignored)."""
    return _dt.date.fromisoformat(s[:10]) if s else None


def _build_index():
    """pid -> [(start_date, stop_or_None), ...] for NSAID rows, both CSV runs."""
    idx = {}
    for path in CSV_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            r = csv.reader(fh)
            next(r, None)  # header
            for row in r:
                if len(row) <= _DESC:
                    continue
                if not any(n in row[_DESC].lower() for n in NSAIDS):
                    continue
                idx.setdefault(row[_PATIENT], []).append(
                    (_date(row[_START]), _date(row[_STOP])))
    return idx


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def chronicity(pid):
    """{courses, cumulative_days, max_course_days, ongoing, chronic} for one patient."""
    rows = _index().get(pid, [])
    durations = [(stop - start).days for start, stop in rows
                 if start is not None and stop is not None]
    cumulative = sum(durations)
    max_course = max(durations) if durations else 0
    courses = len(rows)
    ongoing = any(stop is None for _, stop in rows)   # open-ended = still on it -> chronic
    chronic = (ongoing
               or cumulative > CUMULATIVE_DAYS
               or courses >= COURSES
               or max_course > SINGLE_COURSE_DAYS)
    return {"courses": courses, "cumulative_days": cumulative,
            "max_course_days": max_course, "ongoing": ongoing, "chronic": chronic}


# ── graph-native chronicity (FHIR only, no CSV) ─────────────────────────────────────────
# The FHIR MedicationRequest carries a categorical `status` (active / completed) but NO stop
# date, so the graph supports two of the four arms -- >=3 courses and ongoing
# (status='active') -- but not the duration arms (cumulative >90d, single course >30d), which
# need the CSV. In this data status maps 1:1 to the CSV STOP: `active` == empty STOP
# (ongoing), `completed` == filled STOP. Use this for a CSV-free, purely FHIR-native
# chronicity (e.g. to gate the CRS); use chronicity() for the full CSV oracle rule.
_NSAID_RE = ".*(" + "|".join(NSAIDS) + ").*"
_Q_NSAID_GRAPH = (
    "MATCH (p:Patient {uid:$pid})<-[:SUBJECT]-(mr:MedicationRequest)-[:MEDICATION]->(x) "
    "OPTIONAL MATCH (x)-[:CODE]->(mc:Code) "
    "WITH mr, coalesce(mc.display, CASE WHEN x:Code THEN x.display END) AS name "
    "WHERE name IS NOT NULL AND toLower(name) =~ '" + _NSAID_RE + "' "
    "RETURN count(mr) AS courses, "
    "sum(CASE WHEN mr.status = 'active' THEN 1 ELSE 0 END) AS active"
)


def chronicity_graph(session, pid):
    """FHIR-native NSAID chronicity read from the GRAPH (pass a Neo4j session), no CSV.
    Returns {courses, ongoing, chronic}, where chronic = (>=3 courses) OR (any active
    prescription). Covers the >=3-courses and ongoing arms only; the duration arms need
    chronicity() (CSV)."""
    r = session.run(_Q_NSAID_GRAPH, pid=pid).single()
    courses = r["courses"] if r and r["courses"] is not None else 0
    ongoing = bool(r["active"]) if r and r["active"] is not None else False
    return {"courses": courses, "ongoing": ongoing, "chronic": ongoing or courses >= COURSES}


if __name__ == "__main__":
    import sys
    for pid in sys.argv[1:]:
        print(pid, chronicity(pid))
