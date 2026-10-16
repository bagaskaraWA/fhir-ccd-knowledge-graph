r"""
make_chart.py
=============
Source-record extract for the clinician review: a readable chart for each reviewed
patient, built so an expert can verify what the briefing asserts.

NON-CIRCULARITY: this reads the RAW FHIR bundle -- never Neo4j, never the CRS output.
It reuses silver_oracle's bundle index so the source is byte-identical to the one the
reference standard reads. A loader or graph defect is therefore visible to the reviewer
rather than hidden from them. (eval/clinical_<pid>.md, by contrast, is graph-derived and
is a labelling aid, not a source record.)

Scope: a verbatim dump is not usable -- one CCD patient carries ~250 conditions, ~660
medication requests and ~6,900 observations (150+ printed pages). This emits a
claim-checkable extract instead:

  * conditions   -- all, with onset / resolved dates
  * medications  -- deduplicated by drug, with first/last authored date, FHIR status,
                    and number of requests
  * key labs     -- full trajectory for the values the guideline logic turns on
  * procedures   -- deduplicated, with counts and date range
  * care plans / allergies -- all (small)
  * encounters / other observations -- summary counts only

NOTE ON MEDICATION DATES: FHIR MedicationRequest carries `authoredOn` and a categorical
`status`, but NO stop date. "Last authored" is therefore the last time the drug was
PRESCRIBED, not the date it was stopped. This is stated in the output so a reviewer does
not read it as a discontinuation date.

Runs in .venv (stdlib only).
Usage:
    python make_chart.py <pid> [<pid> ...]      # one file per patient
    python make_chart.py --review               # the five reviewed patients
"""
import argparse
import collections
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import silver_oracle as G  # noqa: E402  -- reuse the RAW-bundle index (non-circular)

OUT_DIR = os.path.join(BASE, "clinician_review", "charts")

TRAJECTORY = 6   # readings shown per analyte after the summary table

PACKET_DIR = os.path.join(BASE, "clinician_review")


def review_patients():
    """[(n, pid)] taken from the existing packet filenames.

    The chart number MUST match the packet number: a reviewer handed "Patient 3" and
    "Chart 3" has to be looking at one patient. Deriving the numbering from
    patient_<n>_<pid8>.md rather than from a list here keeps the two in step even if
    the packet order is regenerated.
    """
    out = []
    for f in sorted(os.listdir(PACKET_DIR)):
        if not (f.startswith("patient_") and f.endswith(".md")):
            continue
        stem = f[len("patient_"):-len(".md")]
        num, _, pid8 = stem.partition("_")
        if not num.isdigit() or not pid8:
            continue
        full = [p for p in G.BUNDLES if p.startswith(pid8)]
        if len(full) == 1:
            out.append((int(num), full[0]))
        else:
            print(f"  !! packet {f}: {len(full)} bundles match {pid8}", file=sys.stderr)
    return sorted(out)

# Observations the guideline logic turns on -- shown with their full trajectory.
# Matched as lower-cased substrings against the observation display name. Synthea's
# LOINC display names are not the colloquial ones -- LDL is "Cholesterol in LDL ...",
# triglycerides is singular, and blood pressure is a PANEL whose systolic/diastolic
# readings live in `component`. Match the names that actually occur.
KEY_OBS = (
    "left ventricular ejection fraction",
    "cholesterol in ldl", "low density lipoprotein",
    "triglyceride",                       # singular: matches "Triglyceride [Mass/volume]"
    "cholesterol in hdl", "hdl cholesterol",
    "total cholesterol", "cholesterol [mass/volume]",
    "hemoglobin a1c", "glucose",
    "glomerular filtration", "creatinine",
    "body mass index",
    "blood pressure panel",               # components carry systolic/diastolic
    "tobacco smoking status",
)


def _disp(cc):
    """Display text of a CodeableConcept."""
    if not isinstance(cc, dict):
        return None
    if cc.get("text"):
        return cc["text"]
    for c in cc.get("coding") or []:
        if c.get("display"):
            return c["display"]
    return None


def _date(*vals):
    """First non-empty value, trimmed to YYYY-MM-DD."""
    for v in vals:
        if isinstance(v, str) and v:
            return v[:10]
    return ""


def _resources(bundle):
    for e in bundle.get("entry") or []:
        r = e.get("resource")
        if r:
            yield e.get("fullUrl", ""), r


def _by_type(bundle):
    out = collections.defaultdict(list)
    ids = {}
    for full, r in _resources(bundle):
        out[r.get("resourceType")].append(r)
        if full:
            ids[full] = r
        if r.get("id"):
            ids[r["resourceType"] + "/" + r["id"]] = r
    return out, ids


def _reason(res, ids):
    """Resolve reasonReference / reasonCode to a display string."""
    for ref in res.get("reasonReference") or []:
        t = ids.get(ref.get("reference", ""))
        if t:
            d = _disp(t.get("code"))
            if d:
                return d
    for cc in res.get("reasonCode") or []:
        d = _disp(cc)
        if d:
            return d
    return ""


def _med_name(mr, ids):
    d = _disp(mr.get("medicationCodeableConcept"))
    if d:
        return d
    ref = (mr.get("medicationReference") or {}).get("reference", "")
    t = ids.get(ref)
    return _disp(t.get("code")) if t else "(unresolved medication reference)"


def _obs_value(o):
    q = o.get("valueQuantity")
    if q and q.get("value") is not None:
        return f"{q['value']} {q.get('unit', '')}".strip()
    if _disp(o.get("valueCodeableConcept")):
        return _disp(o["valueCodeableConcept"])
    if o.get("valueString"):
        return o["valueString"]
    parts = []
    for c in o.get("component") or []:
        n, v = _disp(c.get("code")), c.get("valueQuantity")
        if n and v and v.get("value") is not None:
            parts.append(f"{n} {v['value']} {v.get('unit', '')}".strip())
    return "; ".join(parts)


def build(pid):
    bundle = G._load(pid)
    res, ids = _by_type(bundle)
    L = []
    w = L.append

    # ---- header -------------------------------------------------------------
    pat = (res.get("Patient") or [{}])[0]
    nm = (pat.get("name") or [{}])[0]
    name = " ".join((nm.get("given") or []) + [nm.get("family", "")]).strip()
    born = pat.get("birthDate", "")
    died = _date(pat.get("deceasedDateTime"))
    encs = res.get("Encounter", [])
    enc_dates = sorted(_date((e.get("period") or {}).get("start")) for e in encs if
                       _date((e.get("period") or {}).get("start")))
    chart_date = enc_dates[-1] if enc_dates else ""
    age = ""
    if born and chart_date:
        age = int(chart_date[:4]) - int(born[:4]) - (
            (chart_date[5:10] < born[5:10]) if len(born) >= 10 else 0)

    w(f"# SOURCE RECORD -- {name or pid[:8]}")
    w("")
    w("```")
    w(f"Patient ID    : {pid}")
    w(f"Name          : {name}")
    w(f"Gender        : {pat.get('gender', '')}")
    w(f"Birth date    : {born}")
    w(f"Chart date    : {chart_date}   (date of the most recent encounter)")
    w(f"Age at chart  : {age}")
    if died:
        w(f"Deceased      : {died}")
    w(f"Marital status: {_disp(pat.get('maritalStatus')) or ''}")
    w("```")
    w("")
    w("> Extracted directly from the raw FHIR R4 bundle -- not from the knowledge graph "
      "and not from the decision-support output. Use it to verify the briefing "
      "independently of the system that produced it.")
    w("")

    # ---- allergies ----------------------------------------------------------
    w("## ALLERGIES")
    w("")
    al = res.get("AllergyIntolerance", [])
    if not al:
        w("None recorded.")
    else:
        for a in al:
            w(f"- {_date(a.get('recordedDate'))} : {_disp(a.get('code')) or '(unnamed)'}")
    w("")

    # ---- conditions ---------------------------------------------------------
    conds = res.get("Condition", [])
    w(f"## CONDITIONS ({len(conds)})")
    w("")
    w("`onset -- resolved` (blank resolved = still active)")
    w("")
    rows = []
    for c in conds:
        rows.append((_date(c.get("onsetDateTime")),
                     _date(c.get("abatementDateTime")),
                     _disp(c.get("code")) or "(unnamed)"))
    for on, off, nm_ in sorted(rows, reverse=True):
        w(f"- `{on or '??????????'} -- {off or '          '}` {nm_}")
    w("")

    # ---- medications --------------------------------------------------------
    mrs = res.get("MedicationRequest", [])
    agg = collections.OrderedDict()
    for m in mrs:
        nm_ = _med_name(m, ids)
        d = _date(m.get("authoredOn"))
        a = agg.setdefault(nm_, {"n": 0, "first": d, "last": d,
                                 "status": set(), "reason": _reason(m, ids)})
        a["n"] += 1
        if d:
            a["first"] = min(a["first"] or d, d)
            a["last"] = max(a["last"] or d, d)
        if m.get("status"):
            a["status"].add(m["status"])
    w(f"## MEDICATIONS ({len(agg)} distinct drugs, {len(mrs)} requests)")
    w("")
    w("> FHIR carries `authoredOn` and a categorical `status`, but **no stop date**. "
      "`last` is the last date the drug was *prescribed*, not the date it was stopped.")
    w("")
    for nm_, a in sorted(agg.items(), key=lambda kv: kv[1]["last"], reverse=True):
        st = "/".join(sorted(a["status"])) or "?"
        rsn = f"  -- for {a['reason']}" if a["reason"] else ""
        w(f"- `{a['first']} .. {a['last']}` [{st.upper()}] x{a['n']} : {nm_}{rsn}")
    w("")

    # ---- key labs -----------------------------------------------------------
    obs = res.get("Observation", [])
    key = collections.defaultdict(list)
    for o in obs:
        nm_ = _disp(o.get("code")) or ""
        low = nm_.lower()
        if any(k in low for k in KEY_OBS):
            v = _obs_value(o)
            if v:
                key[nm_].append((_date(o.get("effectiveDateTime")), v))
    n_key = sum(len(v) for v in key.values())
    w(f"## KEY LABS AND VITALS  ({n_key} values over {len(key)} analytes)")
    w("")
    w("The guideline logic aggregates these: **worst-ever** for laboratory values, "
      "**most recent** for blood pressure and smoking status. Both aggregates are shown "
      "below so a recommendation can be checked without scanning every reading. The last "
      f"{TRAJECTORY} readings of each analyte follow the table.")
    w("")
    w("| Analyte | n | first | last | most recent | min | max |")
    w("|---|---:|---|---|---|---:|---:|")
    for nm_ in sorted(key):
        vals = sorted(key[nm_], reverse=True)          # newest first
        nums = []
        for _, v in vals:
            try:
                nums.append(float(str(v).split()[0]))
            except (ValueError, IndexError):
                pass
        lo = f"{min(nums):g}" if nums else "--"
        hi = f"{max(nums):g}" if nums else "--"
        w(f"| {nm_} | {len(vals)} | {vals[-1][0]} | {vals[0][0]} "
          f"| {vals[0][1]} | {lo} | {hi} |")
    w("")
    for nm_ in sorted(key):
        vals = sorted(key[nm_], reverse=True)[:TRAJECTORY]
        w(f"**{nm_}** -- last {len(vals)}")
        w("")
        w("```")
        for d, v in vals:
            w(f"  {d}   {v}")
        w("```")
        w("")

    # ---- procedures ---------------------------------------------------------
    procs = res.get("Procedure", [])
    pagg = collections.OrderedDict()
    for p in procs:
        nm_ = _disp(p.get("code")) or "(unnamed)"
        d = _date(p.get("performedDateTime"), (p.get("performedPeriod") or {}).get("start"))
        a = pagg.setdefault(nm_, {"n": 0, "first": d, "last": d})
        a["n"] += 1
        if d:
            a["first"] = min(a["first"] or d, d)
            a["last"] = max(a["last"] or d, d)
    w(f"## PROCEDURES ({len(pagg)} distinct, {len(procs)} total)")
    w("")
    for nm_, a in sorted(pagg.items(), key=lambda kv: kv[1]["last"], reverse=True):
        w(f"- `{a['first']} .. {a['last']}` x{a['n']} : {nm_}")
    w("")

    # ---- care plans ---------------------------------------------------------
    cps = res.get("CarePlan", [])
    w(f"## CARE PLANS ({len(cps)})")
    w("")
    for c in cps:
        d = _date((c.get("period") or {}).get("start"))
        cat = "; ".join(filter(None, (_disp(x) for x in c.get("category") or []))) or "(uncategorised)"
        w(f"- `{d}` [{(c.get('status') or '?').upper()}] {cat}")
        r = _reason(c, ids)
        if r:
            w(f"    - reason: {r}")
        for act in c.get("activity") or []:
            dn = _disp((act.get("detail") or {}).get("code"))
            if dn:
                w(f"    - activity: {dn}")
    w("")

    # ---- summary of what is NOT itemised ------------------------------------
    other = len(obs) - sum(len(v) for v in key.values())
    w("## NOT ITEMISED ABOVE")
    w("")
    w(f"- Encounters: {len(encs)}"
      + (f" ({enc_dates[0]} .. {enc_dates[-1]})" if enc_dates else ""))
    w(f"- Other observations: {other} routine values not used by the guideline logic")
    w("")
    w("These are present in the source bundle and were omitted only for length; "
      "ask if any is needed to settle a judgement.")
    w("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pids", nargs="*", help="patient uuids")
    ap.add_argument("--review", action="store_true",
                    help="the reviewed patients, numbered to match the review packets")
    a = ap.parse_args()
    if a.review:
        numbered = review_patients()
    else:
        numbered = list(enumerate(a.pids, 1))
    if not numbered:
        ap.error("give patient ids or --review")
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, pid in numbered:
        if pid not in G.BUNDLES:
            print(f"  !! no bundle for {pid}", file=sys.stderr)
            continue
        txt = build(pid)
        out = os.path.join(OUT_DIR, f"chart_{i}_{pid[:8]}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"  wrote {out}  ({len(txt.splitlines())} lines)")


if __name__ == "__main__":
    main()
