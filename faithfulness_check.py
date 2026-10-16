r"""
faithfulness_check.py
=====================
Citation-level faithfulness check for the grounded-briefing demo (Option B).
For each patient that has saved eval/briefing_facts_<pid>.json +
eval/briefing_<pid>.md (produced by `crs_briefing.py <pid> --save`, or the OpenAI
twin), it compares the LLM briefing against the retrieved facts and flags:

  FABRICATED recs  -- a recommendation id cited in the briefing that is NOT in
                      the facts  (hallucination -- the critical failure).
  FABRICATED PMIDs -- a PMID cited in the briefing that is NOT in the facts.
  OMITTED recs     -- an applicable/safety rec in the facts the briefing never
                      mentions (completeness gap).
  OAC OVER-CLAIM   -- the briefing asserts the patient is "on/requires oral
                      anticoagulation" (the APT:11-16 precondition) when NO
                      anticoagulant is in the facts' `medications`. A conditional
                      phrasing ("if on/requiring oral anticoagulation: ...") is OK.

Most prose-level "unsupported clinical claim" checks still need a human read; this
tool covers the objective citable part PLUS the one recurring over-claim above.

Runs in .venv (stdlib only).
Usage:
    .\.venv\Scripts\python.exe faithfulness_check.py
"""
import json
import glob
import os
import re

EVAL = "eval"
REC_RE = re.compile(r"[A-Z]{2,5}[0-9]?:[0-9]+(?::[0-9]+)?")   # APT:1, SGLT2:4, CR:1:1, TP:3:1
PMID_RE = re.compile(r"\b\d{7,9}\b")                          # PubMed IDs are 7-9 digits


OAC_MEDS = ("warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban")
# asserts the patient is on/requires anticoagulation (vs the allowed conditional "if ...")
OAC_ASSERT = re.compile(r"\b(on|requires?|requiring|post-\w+ on)\b[^.\n]{0,25}anticoagula", re.I)
# Section boundaries. Headers vary in case and punctuation across runs -- "**2. WHY THESE
# APPLY**", "**5. WHY THESE APPLY:**", "**4. Why these apply**" all occur -- so match the
# stem, not the exact string.
SECTION_START = re.compile(r"^\s*(?:\*\*\s*\d+\.|#)")
TRACE_SECTION = re.compile(r"^\s*\*\*\s*\d+\.\s*why\s+these\s+apply", re.I)


def short(recid):
    return recid.replace("CCD-2023:", "")


def oac_overclaim(facts, text):
    """Lines that assert anticoagulation as fact while no OAC is in `medications`.

    Scoped to the ACTIONABLE part of the briefing. The WHY-THESE-APPLY section is a
    provenance trace explaining which condition triggered each recommendation; it is
    excluded, because an assertion there is not something a reader acts on, and because
    the hedges it uses are phrased freely.

    That exclusion was added after a 30-briefing run flagged 10 lines across 4 briefings,
    all of them false positives of the same shape:

        ACTIONS       "If on/requiring oral anticoagulation: DAPT 1-4 weeks ..."   passes
        WHY-THEY-APPLY "APT:11 -- ... conditional on oral anticoagulation need
                        (not confirmed in current medications)"                    flagged

    OAC_ASSERT matched the "on" inside "conditional on", while the exemption below only
    recognises the literal "if on" / "if requir" -- so the check fired on the hedge itself.
    The trace hits are still returned separately and reported, so the count stays visible
    rather than silently dropped.
    """
    meds = " ".join(m.get("name", "") for m in facts.get("medications", [])).lower()
    if any(o in meds for o in OAC_MEDS):
        return [], []                   # patient IS on an OAC -> the claim is supported

    hits, trace_hits, in_trace = [], [], False
    for line in text.splitlines():
        if SECTION_START.match(line):
            in_trace = bool(TRACE_SECTION.match(line))
        low = line.lower()
        if OAC_ASSERT.search(low) and "if on" not in low and "if requir" not in low:
            (trace_hits if in_trace else hits).append(line.strip())
    return hits, trace_hits


def facts_recs_pmids(facts):
    recs, pmids = set(), set()
    for item in facts.get("applicable", []):
        recs.add(short(item.get("recId", "")))
        for p in (item.get("citedPmids") or []):
            pmids.add(str(p))
    for item in facts.get("safetyFlags", []):
        recs.add(short(item.get("recId", "")))
    recs.discard("")
    return recs, pmids


def main():
    fact_files = sorted(glob.glob(os.path.join(EVAL, "briefing_facts_*.json")))
    if not fact_files:
        raise SystemExit("No eval/briefing_facts_*.json -- run "
                         "`crs_briefing.py <pid> --save` for a few patients first.")

    tot_fab_rec = tot_fab_pmid = tot_omit = tot_oac = tot_oac_trace = 0
    print(f"{'patient':<10}{'factRecs':>9}{'omitted':>9}{'fabRec':>8}{'fabPMID':>9}{'oac':>5}  verdict")
    for ff in fact_files:
        pid = os.path.basename(ff)[len("briefing_facts_"):-len(".json")]
        bf = os.path.join(EVAL, f"briefing_{pid}.md")
        if not os.path.exists(bf):
            print(f"{pid[:8]:<10}  (no briefing_{pid}.md -- run without --no-llm)")
            continue
        facts = json.load(open(ff, encoding="utf-8"))
        f_recs, f_pmids = facts_recs_pmids(facts)
        text = open(bf, encoding="utf-8").read()

        brief_recs = set(REC_RE.findall(text))
        brief_pmids = set(PMID_RE.findall(text))

        fab_recs = sorted(r for r in brief_recs if r not in f_recs)
        omit_recs = sorted(r for r in f_recs if r not in brief_recs)
        fab_pmids = sorted(p for p in brief_pmids if p not in f_pmids)
        oac, oac_trace = oac_overclaim(facts, text)

        tot_fab_rec += len(fab_recs); tot_fab_pmid += len(fab_pmids)
        tot_omit += len(omit_recs); tot_oac += len(oac); tot_oac_trace += len(oac_trace)
        verdict = "FAITHFUL" if not (fab_recs or fab_pmids or oac) else "** UNFAITHFUL **"
        print(f"{pid[:8]:<10}{len(f_recs):>9}{len(omit_recs):>9}{len(fab_recs):>8}"
              f"{len(fab_pmids):>9}{len(oac):>5}  {verdict}")
        if fab_recs:  print(f"           fabricated recs : {fab_recs}")
        if fab_pmids: print(f"           fabricated PMIDs: {fab_pmids}")
        if omit_recs: print(f"           omitted recs    : {omit_recs}")
        if oac:       print(f"           OAC over-claim  : {oac}")
        if oac_trace: print(f"           (trace-only, not counted: {len(oac_trace)} hedged mention(s))")

    print("\n" + "=" * 60)
    print(f"TOTAL fabricated recs={tot_fab_rec}  fabricated PMIDs={tot_fab_pmid}  "
          f"omitted recs={tot_omit}  OAC over-claims={tot_oac}")
    if tot_oac_trace:
        print(f"      ({tot_oac_trace} hedged mention(s) in WHY-THESE-APPLY excluded -- "
              "provenance trace, not an actionable claim; see oac_overclaim docstring)")
    print("Fabrications + OAC over-claims MUST be 0 for a faithful grounded summarizer.")
    print("Omissions are a completeness signal (tune USER_TEMPLATE if high).")


if __name__ == "__main__":
    main()
