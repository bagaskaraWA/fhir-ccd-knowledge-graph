# -*- coding: utf-8 -*-
r"""Render a patient's FHIR bundle as a neutral, unfiltered clinical record.

Written for the clinician review packet. It deliberately does NOT reuse
eval/clinical_<pid>.md, which was built for gold-standard labelling and carries the
system's own reasoning: it shows only the gated observations, states derived verdicts
(``-> chronic NSAID : yes``), and names the rules a finding drives (``PCI ... -> drives
APT:2``). A rater given that document cannot judge completeness independently, because it
has already told them what matters.

This reads the FHIR bundle directly -- not Neo4j, not silver_oracle, not obs_gate -- so
the packet's data path is independent of both the system under review and the reference
oracle.

Two principles:

  AGGREGATE REPETITION.  A bundle carries thousands of Observation resources over ~80
  distinct codes. Each code is collapsed to one row (n, first, last, range, most recent).
  Collapsing 200 blood pressures loses nothing a clinician needs.

  FILTER NO CLINICAL CATEGORY.  Every distinct condition, procedure, medication and
  observation code is listed -- not the nine the system gates on. This is the whole point:
  the rater must be able to notice that the briefing ignored something.

Only administrative resources are dropped (see SKIP), and the rendering says so in the
document itself rather than dropping them silently.

Usage:
    python telaah-klinisi/buat_rekam_medis.py <patientId> [<patientId> ...]
    python telaah-klinisi/buat_rekam_medis.py --from-briefings
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FHIR_DIR = os.environ.get("FHIR_DIR", os.path.join(BASE, "sihd+general", "fhir"))
OUT_DIR = os.path.join(BASE, "telaah-klinisi", "paket")

# Administrative only -- no clinical content. Disclosed in the rendered header.
SKIP = {"Claim", "ExplanationOfBenefit", "SupplyDelivery", "DocumentReference",
        "Provenance", "ImagingStudy", "Coverage"}

# The element holding the coded concept is named per resource type; assuming "code"
# everywhere silently renders Immunization as "?".
LAIN = (("AllergyIntolerance", "Alergi", "code"),
        ("Immunization", "Imunisasi", "vaccineCode"))


def disp(concept):
    if not isinstance(concept, dict):
        return None
    if concept.get("text"):
        return concept["text"]
    for c in concept.get("coding", []):
        if c.get("display"):
            return c["display"]
        if c.get("code"):
            return c["code"]
    return None


def code_of(concept):
    for c in (concept or {}).get("coding", []):
        if c.get("code"):
            return c["code"]
    return ""


def day(s):
    return (s or "")[:10]


def usia(birth, ref):
    """Whole years between two YYYY-MM-DD dates, or None if either is missing/malformed."""
    try:
        by, bm, bd = (int(x) for x in birth[:10].split("-"))
        ry, rm, rd = (int(x) for x in ref[:10].split("-"))
    except (ValueError, AttributeError, TypeError):
        return None
    years = ry - by - ((rm, rd) < (bm, bd))
    return years if 0 <= years < 130 else None


def obs_value(r):
    """Return [(label, value, unit)] -- handles scalar and component observations."""
    if "valueQuantity" in r:
        q = r["valueQuantity"]
        return [("", q.get("value"), q.get("unit", ""))]
    if "valueCodeableConcept" in r:
        return [("", disp(r["valueCodeableConcept"]), "")]
    if "valueString" in r:
        return [("", r["valueString"], "")]
    out = []
    for comp in r.get("component", []):
        q = comp.get("valueQuantity") or {}
        v = q.get("value") if q else disp(comp.get("valueCodeableConcept"))
        out.append((disp(comp.get("code")) or "?", v, q.get("unit", "")))
    return out


def collect(bundle):
    res = collections.defaultdict(list)
    for e in bundle.get("entry", []):
        r = e.get("resource")
        if r and r.get("resourceType") not in SKIP:
            res[r["resourceType"]].append(r)
    return res


def patient_name(bundle):
    """Synthea's synthetic name, digit suffixes stripped: 'Eugene421 Cormier289' -> 'Eugene Cormier'."""
    for e in bundle.get("entry", []):
        r = e.get("resource", {})
        if r.get("resourceType") == "Patient" and r.get("name"):
            n = r["name"][0]
            raw = " ".join(list(n.get("given", [])) + [n.get("family", "")])
            return re.sub(r"\s+", " ", re.sub(r"\d+", "", raw)).strip(), r
    return "(tanpa nama)", {}


def sections(bundle):
    """Structured record: {demografi, kondisi, prosedur, obat, lain, observasi}.

    Repetition is aggregated (one row per code); no clinical category is filtered.
    """
    R = collect(bundle)
    name, pat = patient_name(bundle)

    enc = R.get("Encounter", [])
    dates = sorted(d for d in (day((e.get("period") or {}).get("start")) for e in enc) if d)
    birth, died = pat.get("birthDate", ""), day(pat.get("deceasedDateTime", ""))

    # Age is quoted against the last recorded encounter, not today: these records end at
    # different dates, and a chart's "current" age is the age at its last entry. For a
    # deceased patient the row says so instead, with the age reached at death.
    if died:
        n = usia(birth, died)
        umur = "Meninggal %s%s" % (died, " (usia %d tahun)" % n if n is not None else "")
    elif dates:
        n = usia(birth, dates[-1])
        umur = "%d tahun (per kunjungan terakhir)" % n if n is not None else "-"
    else:
        umur = "-"

    demografi = [("Nama (sintetis)", name or "-"),
                 ("Jenis kelamin", pat.get("gender", "-")),
                 ("Tanggal lahir", birth or "-"),
                 ("Usia", umur)]
    if dates:
        demografi.append(("Rentang rekam",
                          "%s s.d. %s (%d kunjungan)" % (dates[0], dates[-1], len(enc))))

    conds = {}
    for c in R.get("Condition", []):
        k = disp(c.get("code")) or "?"
        d = day(c.get("onsetDateTime") or c.get("recordedDate"))
        st = disp(c.get("clinicalStatus")) or ""
        if k not in conds or (d and d < conds[k][0]):
            conds[k] = (d, st)
    kondisi = [(d or "-", k, st or "-")
               for k, (d, st) in sorted(conds.items(), key=lambda kv: (kv[1][0] or "9999", kv[0]))]

    procs = {}
    for p in R.get("Procedure", []):
        k = disp(p.get("code")) or "?"
        d = day(p.get("performedDateTime") or (p.get("performedPeriod") or {}).get("start"))
        n, first, last = procs.get(k, (0, None, None))
        procs[k] = (n + 1,
                    min(x for x in (first, d) if x) if (first or d) else None,
                    max(x for x in (last, d) if x) if (last or d) else None)
    prosedur = [(k, str(n), f or "-", l or "-")
                for k, (n, f, l) in sorted(procs.items(), key=lambda kv: (kv[1][1] or "9999", kv[0]))]

    inline = {m.get("id"): disp(m.get("code")) for m in R.get("Medication", [])}
    meds = {}
    for m in R.get("MedicationRequest", []):
        k = disp(m.get("medicationCodeableConcept"))
        if not k:
            ref = ((m.get("medicationReference") or {}).get("reference") or "").split("/")[-1]
            ref = ref.split(":")[-1]
            k = inline.get(ref) or "(rujukan obat: %s)" % (ref[:8] or "?")
        d = day(m.get("authoredOn"))
        n, first, last, sts = meds.get(k, (0, None, None, set()))
        sts.add(m.get("status", ""))
        meds[k] = (n + 1,
                   min(x for x in (first, d) if x) if (first or d) else None,
                   max(x for x in (last, d) if x) if (last or d) else None, sts)
    obat = [(k, str(n), f or "-", l or "-", ", ".join(sorted(s for s in sts if s)) or "-")
            for k, (n, f, l, sts) in sorted(meds.items(),
                                            key=lambda kv: (kv[1][2] or "0000", kv[0]), reverse=True)]

    lain = []
    for rtype, title, field in LAIN:
        items = R.get(rtype, [])
        if items:
            seen = collections.Counter(disp(i.get(field)) or "?" for i in items)
            lain.append((title, ["%s%s" % (k, " (%dx)" % n if n > 1 else "")
                                 for k, n in sorted(seen.items())]))

    series = collections.defaultdict(list)
    for o in R.get("Observation", []):
        base = disp(o.get("code")) or "?"
        d = day(o.get("effectiveDateTime") or o.get("issued"))
        for label, val, unit in obs_value(o):
            key = ("%s -- %s" % (base, label)) if label else base
            series[(key, unit or "")].append((d, val))
    observasi = []
    for (key, unit), vals in sorted(series.items()):
        vals.sort(key=lambda t: t[0] or "")
        nums = [v for _, v in vals if isinstance(v, (int, float))]
        last = vals[-1][1]
        observasi.append((key, unit or "-", str(len(vals)), vals[0][0] or "-", vals[-1][0] or "-",
                          "%.1f" % min(nums) if nums else "-",
                          "%.1f" % max(nums) if nums else "-",
                          ("%.1f" % last) if isinstance(last, (int, float))
                          else (str(last)[:40] if last is not None else "-")))

    return {"nama": name, "demografi": demografi, "kondisi": kondisi, "prosedur": prosedur,
            "obat": obat, "lain": lain, "observasi": observasi}


def render(pid, bundle):
    R = collect(bundle)
    L = []
    w = L.append

    w("# Rekam Medis Pasien %s" % pid[:8])
    w("")
    w("Rekam medis **sintetis** (Synthea), disajikan apa adanya dari berkas HL7 FHIR R4.")
    w("Tidak ada penyaringan menurut jenis data: seluruh kondisi, prosedur, obat, dan kode")
    w("observasi yang ada pada rekam ditampilkan. Pengukuran yang berulang diringkas menjadi")
    w("satu baris per kode (jumlah, rentang tanggal, nilai terendah/tertinggi, nilai terakhir).")
    w("")
    w("Tidak diikutsertakan: data administratif dan penagihan (%s)." % ", ".join(sorted(SKIP)))
    w("")

    # ---- demographics (from sections(), so the two renderings cannot drift) ----
    w("| | |")
    w("|---|---|")
    for label, value in sections(bundle)["demografi"]:
        w("| %s | %s |" % (label, value))
    w("")

    # ---- conditions ----
    conds = {}
    for c in R.get("Condition", []):
        k = disp(c.get("code")) or "?"
        d = day(c.get("onsetDateTime") or c.get("recordedDate"))
        st = disp(c.get("clinicalStatus")) or ""
        prev = conds.get(k)
        if prev is None or (d and d < prev[0]):
            conds[k] = (d, st)
    w("## Kondisi/Diagnosis (%d)" % len(conds))
    w("")
    w("| Onset | Kondisi | Status |")
    w("|---|---|---|")
    for k, (d, st) in sorted(conds.items(), key=lambda kv: (kv[1][0] or "9999", kv[0])):
        w("| %s | %s | %s |" % (d or "-", k, st or "-"))
    w("")

    # ---- procedures ----
    procs = {}
    for p in R.get("Procedure", []):
        k = disp(p.get("code")) or "?"
        d = day(p.get("performedDateTime") or (p.get("performedPeriod") or {}).get("start"))
        n, first, last = procs.get(k, (0, None, None))
        procs[k] = (n + 1, min(x for x in (first, d) if x) if (first or d) else None,
                    max(x for x in (last, d) if x) if (last or d) else None)
    w("## Prosedur/Tindakan (%d jenis)" % len(procs))
    w("")
    w("| Jenis | n | Pertama | Terakhir |")
    w("|---|---|---|---|")
    for k, (n, f, l) in sorted(procs.items(), key=lambda kv: (kv[1][1] or "9999", kv[0])):
        w("| %s | %d | %s | %s |" % (k, n, f or "-", l or "-"))
    w("")

    # ---- medications ----
    meds = {}
    inline = {m.get("id"): disp(m.get("code")) for m in R.get("Medication", [])}
    for m in R.get("MedicationRequest", []):
        k = disp(m.get("medicationCodeableConcept"))
        if not k:
            ref = ((m.get("medicationReference") or {}).get("reference") or "").split("/")[-1]
            ref = ref.split(":")[-1]
            k = inline.get(ref) or "(rujukan obat: %s)" % (ref[:8] or "?")
        d = day(m.get("authoredOn"))
        n, first, last, sts = meds.get(k, (0, None, None, set()))
        sts.add(m.get("status", ""))
        meds[k] = (n + 1,
                   min(x for x in (first, d) if x) if (first or d) else None,
                   max(x for x in (last, d) if x) if (last or d) else None, sts)
    w("## Obat (%d jenis)" % len(meds))
    w("")
    w("| Obat | Resep | Pertama | Terakhir | Status |")
    w("|---|---|---|---|---|")
    for k, (n, f, l, sts) in sorted(meds.items(), key=lambda kv: (kv[1][2] or "0000", kv[0]),
                                    reverse=True):
        w("| %s | %d | %s | %s | %s |" % (k, n, f or "-", l or "-",
                                          ", ".join(sorted(s for s in sts if s)) or "-"))
    w("")

    # ---- allergies / immunizations, when present ----
    for rtype, title, field in LAIN:
        items = R.get(rtype, [])
        if not items:
            continue
        seen = collections.Counter(disp(i.get(field)) or "?" for i in items)
        w("## %s (%d)" % (title, len(seen)))
        w("")
        for k, n in sorted(seen.items()):
            w("- %s%s" % (k, " (%dx)" % n if n > 1 else ""))
        w("")

    # ---- observations: every distinct code, repetition aggregated ----
    series = collections.defaultdict(list)
    for o in R.get("Observation", []):
        base = disp(o.get("code")) or "?"
        d = day(o.get("effectiveDateTime") or o.get("issued"))
        for label, val, unit in obs_value(o):
            key = ("%s -- %s" % (base, label)) if label else base
            series[(key, unit or "")].append((d, val))

    w("## Observasi dan Hasil Laboratorium (%d kode)" % len(series))
    w("")
    w("Nilai numerik diringkas: n, rentang tanggal, terendah, tertinggi, dan nilai terakhir.")
    w("Nilai non-numerik ditampilkan nilai terakhirnya.")
    w("")
    w("| Pemeriksaan | Satuan | n | Pertama | Terakhir | Min | Maks | Nilai terakhir |")
    w("|---|---|---|---|---|---|---|---|")
    for (key, unit), vals in sorted(series.items()):
        vals.sort(key=lambda t: t[0] or "")
        nums = [v for _, v in vals if isinstance(v, (int, float))]
        last = vals[-1][1]
        lo = "%.1f" % min(nums) if nums else "-"
        hi = "%.1f" % max(nums) if nums else "-"
        lastfmt = ("%.1f" % last) if isinstance(last, (int, float)) else (str(last)[:40] if last is not None else "-")
        w("| %s | %s | %d | %s | %s | %s | %s | %s |"
          % (key, unit or "-", len(vals), vals[0][0] or "-", vals[-1][0] or "-", lo, hi, lastfmt))
    w("")
    return "\n".join(L)


def bundle_for(pid):
    hits = glob.glob(os.path.join(FHIR_DIR, "*%s*.json" % pid))
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pids", nargs="*", help="patient id(s)")
    ap.add_argument("--from-briefings", action="store_true",
                    help="render every patient that has an eval/briefing_<pid>.md")
    ap.add_argument("--from-list", action="store_true",
                    help="render every patient listed in telaah-klinisi/pasien.txt")
    args = ap.parse_args()

    pids = list(args.pids)
    if args.from_briefings:
        pids += [os.path.basename(p)[len("briefing_"):-len(".md")]
                 for p in glob.glob(os.path.join(BASE, "eval", "briefing_*.md"))]
    if args.from_list:
        listing = os.path.join(BASE, "telaah-klinisi", "pasien.txt")
        if not os.path.exists(listing):
            ap.error("pasien.txt tidak ditemukan")
        for line in io.open(listing, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                pids.append(line.split()[0])
    if not pids:
        ap.error("berikan patientId, atau pakai --from-list / --from-briefings")

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    ok = 0
    for pid in sorted(set(pids)):
        path = bundle_for(pid)
        if not path:
            print("  LEWAT  %s -- bundle tidak ditemukan di %s" % (pid[:8], FHIR_DIR))
            continue
        with io.open(path, encoding="utf-8") as fh:
            text = render(pid, json.load(fh))
        out = os.path.join(OUT_DIR, "rekam_%s.md" % pid)
        with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  OK     rekam_%s.md  (%d baris)" % (pid[:8], text.count("\n")))
        ok += 1
    print("\n%d rekam medis ditulis ke %s" % (ok, os.path.relpath(OUT_DIR, BASE)))


if __name__ == "__main__":
    sys.exit(main())
