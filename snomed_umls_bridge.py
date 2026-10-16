"""Prepare CSVs for merging the literature and EHR graphs in Neo4j.

Generates four files in the Neo4j import folder:
  abstracts.csv              — unique PubMed abstracts (pmid)
  concepts.csv               — unique UMLS concepts found in literature
  abstract_concept_edges.csv — Abstract -[MENTIONS]-> Concept edges
  ehr_umls_mapping.csv       — EHR codes (SNOMED / RxNorm) → UMLS CUI via linker

The last file is the bridge: it lets literature_kg.cypher create
SAME_CONCEPT links from a Concept node to an EHR Condition/Medication/CarePlan.

Setup:
    .\.venv311\Scripts\Activate.ps1
    pip install scispacy spacy pandas  (already installed)

Run:
    python snomed_umls_bridge.py
    python snomed_umls_bridge.py --dry-run    # skip the slow linker step
    python snomed_umls_bridge.py --ehr-only   # regenerate ehr_umls_mapping.csv only
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pandas as pd
import spacy
from scispacy.linking import EntityLinker

# Matches a trailing SNOMED-style semantic tag, e.g. ' (disorder)', ' (finding)'.
# Used to drop hierarchy metadata from descriptions before linking — keeping it
# lets the standalone "disorder" token win UMLS linking against the actual concept.
_SNOMED_TAG_RE = re.compile(r"\s*\([^)]+\)\s*$")

# RxNorm strings start with an optional "NN HR" duration prefix (e.g. "24 HR"),
# then the drug name, then a numeric dose. Strip to the active ingredient so we
# match T121 (Pharmacologic Substance) CUIs — the same tier the literature
# pipeline produces from PubMed mentions like "metoprolol" — instead of T200
# (Clinical Drug) CUIs that name a specific formulation and don't appear in
# free-text abstracts.
_RXNORM_DURATION_PREFIX = re.compile(r"^\d+\s+HR\s+", re.IGNORECASE)
_RXNORM_DRUG_NAME       = re.compile(r"^[A-Za-z\-\s,'/]+")


def _strip_snomed_tag(description: str) -> str:
    """'Polyp of colon (disorder)' -> 'Polyp of colon'. RxNorm strings: no-op."""
    return _SNOMED_TAG_RE.sub("", description).strip()


def _simplify_rxnorm(description: str) -> str:
    """'24 HR metoprolol succinate 100 MG ER Oral Tablet' -> 'metoprolol succinate'.

    Falls back to the original string if the pattern doesn't match (e.g. a
    description starting with a number — `0.4 ML ...`). In that case the
    caller still has the full string to try; we just couldn't simplify it.
    """
    desc = _RXNORM_DURATION_PREFIX.sub("", description)
    match = _RXNORM_DRUG_NAME.match(desc)
    if match:
        name = match.group(0).strip(" /,")
        if name:
            return name
    return description

# ── paths ──────────────────────────────────────────────────────────────────────
# The import folder belongs to the DBMS, not the database. Override with env
# NEO4J_IMPORT when running against a different DBMS instance (same pattern as
# MED_CSV in silver_oracle.py); the default is the thesis DBMS and is what every
# ordinary re-run uses.
NEO4J_IMPORT = Path(os.environ.get(
    "NEO4J_IMPORT",
    r"C:\Users\T14s\.Neo4jDesktop2\Data\dbmss"
    r"\dbms-d17cbae3-f941-411e-be37-2876dc8f1ae8\import"
))
LITERATURE_ENTITIES = Path("data/pubmed_ccd_clinical_entities.csv")

# ── linker settings ────────────────────────────────────────────────────────────
MODEL      = "en_core_sci_md"
TOP_K      = 3
THRESHOLD  = 0.75   # looser than clinical NER — concept names link reliably
BATCH_SIZE = 64
N_PROCESS  = 1

# ── semantic-type buckets, by EHR target label ─────────────────────────────────
# Keep in sync with scispacy_clinical_ner.py:SEMANTIC_TYPES. Used to reject
# UMLS matches whose semantic type doesn't fit the source vocabulary — e.g.,
# the "HR" token in a medication description matching "High risk of" (T033)
# would otherwise win on score and corrupt the RxNorm→UMLS mapping.
SEMANTIC_TYPES: dict[str, set[str]] = {
    "Condition": {
        "T047", "T048", "T184", "T046", "T191",
        "T019", "T037", "T049", "T050", "T020", "T033",
    },
    "Medication": {
        "T121", "T200", "T195", "T125", "T129", "T123",
    },
    "CarePlan": {
        "T061", "T060", "T058", "T059", "T063",
        "T065",  # Educational Activity
    },
    # Procedures share TUIs with CarePlan (T061 therapeutic / T060 diagnostic); the
    # distinction is the SOURCE FILE (procedures.csv -> Procedure), not the TUI. Only
    # allow-listed codes are bridged (PROCEDURE_ALLOWLIST) and each is a MANUAL_CUI
    # override, so this bucket only needs to exist to avoid a KeyError.
    "Procedure": {
        "T061", "T060",
    },
}

# Each EHR source CSV maps to a (system, target_label) pair.
# target_label drives both the TUI filter and the SAME_CONCEPT routing in Cypher.
EHR_SOURCES: list[tuple[str, str, str]] = [
    ("conditions.csv",  "SNOMED-CT", "Condition"),
    ("medications.csv", "RxNorm",    "Medication"),
    ("careplans.csv",   "SNOMED-CT", "CarePlan"),
    ("procedures.csv",  "SNOMED-CT", "Procedure"),   # allow-listed codes only
]

# Only these procedure codes are bridged, to avoid ~390 untargeted procedure Concepts.
# PCI is the sole guideline-referenced procedure Synthea emits that is NOT already
# reachable via a condition: CABG bridges through "History of CABG" (a condition), and
# Synthea has no heart-transplant procedure (only kidney). The listed code is a
# MANUAL_CUI override to the guideline's "History of PCI" CUI so the two bridge.
PROCEDURE_ALLOWLIST: set[str] = {
    "415070008",   # Percutaneous coronary intervention -> C1320647 (History of PCI)
    "32413006",    # Transplantation of heart          -> C2029943 (Transplanted heart present)
}

# ── manual CUI overrides ─────────────────────────────────────────────────────────
# Force-map specific EHR codes to a known-correct UMLS CUI, bypassing the
# semantic-type (TUI) filter. Needed where UMLS types the correct concept
# OUTSIDE its source's bucket, making it structurally unreachable by the linker.
#
# e.g. nicotine (C0028040) is typed T109 (Organic Chemical) + T131 (Hazardous
# Substance), with no T121 (Pharmacologic Substance); and T109 is deliberately
# excluded from the Medication bucket (it pulls in metabolites/lipids). The only
# TUI-passing candidates are T200 dose formulations that _simplify_rxnorm is
# meant to avoid -- so the generic concept can only be assigned by hand here.
# Curate any matching guideline target to the SAME CUI so the two bridge.
#
# Keyed (system, code-as-string) -> (cui, name). Override score is 1.0 by
# convention (hand-verified, like an exact alias hit). Reproducible across
# re-runs, unlike hand-editing ehr_umls_mapping.csv (which a re-run overwrites).
MANUAL_CUI: dict[tuple[str, str], tuple[str, str]] = {
    ("RxNorm", "198031"): ("C0028040", "nicotine"),
    # PCI procedure -> the guideline's "History of PCI" finding CUI, so APT:2/3/11/12/13
    # and CR:1:1's PCI arm bridge to patients who UNDERWENT PCI. Synthea emits PCI only
    # as a procedure (never a condition); the two are the same clinical fact.
    ("SNOMED-CT", "415070008"): ("C1320647", "History of percutaneous coronary intervention"),
    # Heart transplant procedure -> the guideline's "Transplanted heart present" FINDING CUI
    # (CR:1:2 target), same finding-vs-act reconciliation as PCI.
    ("SNOMED-CT", "32413006"): ("C2029943", "Transplanted heart present"),
}


# ── helpers ────────────────────────────────────────────────────────────────────

def build_nlp() -> tuple[spacy.language.Language, EntityLinker]:
    nlp = spacy.load(MODEL, disable=["parser", "tagger", "attribute_ruler", "lemmatizer"])
    linker = EntityLinker(
        nlp=nlp, name="umls_linker",
        resolve_abbreviations=False, linker_name="umls",
        max_entities_per_mention=TOP_K, threshold=THRESHOLD,
    )
    return nlp, linker


def _passes_tui_filter(cui: str, linker: EntityLinker, allowed_tuis: set[str]) -> bool:
    """True if the CUI's semantic types intersect the allowed bucket."""
    entity = linker.kb.cui_to_entity.get(cui)
    if entity is None:
        return False
    return bool(set(entity.types) & allowed_tuis)


def _alias_hit(
    description: str,
    linker: EntityLinker,
    allowed_tuis: set[str],
) -> dict | None:
    """Look up an exact alias hit, restricted to allowed TUIs. Score = 1.0."""
    # Try the description verbatim, then stripped of any SNOMED-style ` (disorder)` tail.
    stripped = _strip_snomed_tag(description)
    candidates = [description] if stripped == description else [description, stripped]
    for text in candidates:
        for variant in (text, text.lower()):
            cuis = linker.kb.alias_to_cuis.get(variant)
            if not cuis:
                continue
            for cui in cuis:
                if not _passes_tui_filter(cui, linker, allowed_tuis):
                    continue
                entity = linker.kb.cui_to_entity[cui]
                return {
                    "umls_cui":   cui,
                    "umls_name":  entity.canonical_name,
                    "umls_score": 1.0,
                }
    return None


def _candidate_hit_batch(
    texts: list[str],
    linker: EntityLinker,
    allowed_tuis: set[str],
) -> list[dict | None]:
    """Run scispacy's TF-IDF candidate generator directly on each whole string.

    Bypasses spaCy NER, which doesn't reliably flag bare noun phrases like
    "Polyp of colon" as entity spans (they need sentence context). The
    candidate generator is the same matching engine the linker uses internally
    — character-trigram TF-IDF nearest neighbor against the UMLS alias index —
    just invoked without requiring a detected entity span to trigger it.
    """
    if not texts:
        return []
    try:
        batched = linker.candidate_generator(texts, TOP_K)
    except Exception as exc:                                  # noqa: BLE001
        print(f"    candidate_generator failed ({exc}); falling through")
        return [None] * len(texts)

    hits: list[dict | None] = []
    for candidates in batched:
        hit: dict | None = None
        for cand in candidates:
            if not cand.similarities:
                continue
            score = max(cand.similarities)
            if score < THRESHOLD:
                continue
            if not _passes_tui_filter(cand.concept_id, linker, allowed_tuis):
                continue
            entity = linker.kb.cui_to_entity[cand.concept_id]
            hit = {
                "umls_cui":   cand.concept_id,
                "umls_name":  entity.canonical_name,
                "umls_score": round(float(score), 3),
            }
            break
        hits.append(hit)
    return hits


def lookup_umls_batch(
    descriptions: list[str],
    allowed_tuis: set[str],
    nlp: spacy.language.Language,
    linker: EntityLinker,
) -> list[dict | None]:
    """Match each description to a UMLS CUI in the allowed semantic-type bucket.

    Three passes in order, each gated by the TUI filter:
      1. Exact alias lookup (fast, deterministic, score 1.0).
      2. TF-IDF candidate generator on the stripped description as one string —
         works for structured EHR descriptions like "Polyp of colon" that
         spaCy NER won't flag as entities without sentence context.
      3. NLP + linker fallback, taking the LEFTMOST passing entity — handles
         compound descriptions where multiple distinct concepts are present.
    """
    results: list[dict | None] = []

    # Pass 1: cheap alias lookups for everything.
    needs_more: list[int] = []
    for i, desc in enumerate(descriptions):
        hit = _alias_hit(desc, linker, allowed_tuis)
        results.append(hit)
        if hit is None:
            needs_more.append(i)

    if not needs_more:
        return results

    # Pass 2: candidate generator (TF-IDF on the stripped whole string).
    stripped_for_cand = [_strip_snomed_tag(descriptions[i]) for i in needs_more]
    cand_hits = _candidate_hit_batch(stripped_for_cand, linker, allowed_tuis)

    needs_nlp_idx: list[int] = []
    for slot, hit in zip(needs_more, cand_hits):
        if hit is not None:
            results[slot] = hit
        else:
            needs_nlp_idx.append(slot)

    if not needs_nlp_idx:
        return results

    # Pass 3: only run the slow NLP+linker on descriptions that still missed.
    # Strip SNOMED semantic tags here so the standalone "disorder"/"finding"
    # token can't beat the real concept on score.
    fallback_texts = [_strip_snomed_tag(descriptions[i]) for i in needs_nlp_idx]
    docs = list(nlp.pipe(fallback_texts, batch_size=BATCH_SIZE, n_process=N_PROCESS))

    for slot, doc in zip(needs_nlp_idx, docs):
        linker(doc)
        # RxNorm/SNOMED descriptions have a fixed shape: the clinical concept
        # of interest is the LEFTMOST entity. Dose units that follow ("MG",
        # "MCG", "UNT") happen to match Biologically Active Substances (T123)
        # with near-1.0 confidence because they ARE chemical symbols — picking
        # by score lets them outrank the actual drug name. Picking the leftmost
        # entity whose CUI passes the TUI filter avoids this structurally.
        hit: dict | None = None
        for ent in doc.ents:
            if not ent._.kb_ents:
                continue
            cui, score = ent._.kb_ents[0]
            if score < THRESHOLD:
                continue
            if not _passes_tui_filter(cui, linker, allowed_tuis):
                continue
            entity = linker.kb.cui_to_entity[cui]
            hit = {
                "umls_cui":   cui,
                "umls_name":  entity.canonical_name,
                "umls_score": round(score, 3),
            }
            break

        results[slot] = hit

    return results


# ── literature CSVs ────────────────────────────────────────────────────────────

def generate_literature_csvs(entities: pd.DataFrame, out_dir: Path) -> None:
    """Produce abstracts.csv, concepts.csv, abstract_concept_edges.csv."""

    # abstracts: one row per unique pmid
    abstracts = entities[["pmid"]].drop_duplicates()
    abstracts.to_csv(out_dir / "abstracts.csv", index=False)
    print(f"  abstracts.csv          -- {len(abstracts):,} unique PMIDs")

    # concepts: unique umls_cui. Keep MeSH name only when the MeSH linker
    # agreed with the UMLS linker on the concept identity — scispacy's MeSH
    # KB uses UMLS CUIs as concept_ids, so mesh_id != umls_cui means the two
    # linkers picked DIFFERENT concepts for the same entity span (not synonyms).
    # Drop mesh_id itself: when valid it equals umls_cui, when invalid it lies.
    concepts_all = entities[["umls_cui", "umls_name", "umls_types", "mesh_id", "mesh_name"]].copy()
    disagree = concepts_all["mesh_id"] != concepts_all["umls_cui"]
    concepts_all.loc[disagree, "mesh_id"]   = None
    concepts_all.loc[disagree, "mesh_name"] = None

    concepts_with_mesh = concepts_all.dropna(subset=["mesh_name"])
    concepts_no_mesh   = concepts_all[concepts_all["mesh_name"].isna()]
    concepts = (
        pd.concat([concepts_with_mesh, concepts_no_mesh])
        .drop_duplicates(subset=["umls_cui"], keep="first")
        .drop(columns=["mesh_id"])
        .reset_index(drop=True)
    )
    with_mesh = concepts["mesh_name"].notna().sum()
    concepts.to_csv(out_dir / "concepts.csv", index=False)
    print(f"  concepts.csv           -- {len(concepts):,} unique UMLS concepts "
          f"({with_mesh} with MeSH name)")

    # edges: one row per (pmid, umls_cui, category) with mention count
    edges = (
        entities.groupby(["pmid", "umls_cui", "category"])
        .size()
        .reset_index(name="mention_count")
    )
    edges.to_csv(out_dir / "abstract_concept_edges.csv", index=False)
    print(f"  abstract_concept_edges -- {len(edges):,} Abstract->Concept edges")


# ── EHR mapping CSV ────────────────────────────────────────────────────────────

def _load_ehr_source(import_dir: Path, csv_name: str, system: str, target_label: str) -> pd.DataFrame:
    """Read one EHR CSV, dedup by code, attach system + target_label columns."""
    df = pd.read_csv(import_dir / csv_name)
    desc_col = "description" if "description" in df.columns else "descriptionName"
    df = df[["code", desc_col]].rename(columns={desc_col: "description"}).copy()
    df["system"]       = system
    df["target_label"] = target_label
    df = df.dropna(subset=["code", "description"]).drop_duplicates(subset=["code"])
    return df.reset_index(drop=True)


def generate_ehr_mapping(
    import_dir: Path,
    out_dir: Path,
    nlp: spacy.language.Language | None,
    linker: EntityLinker | None,
    dry_run: bool,
) -> None:
    """Produce ehr_umls_mapping.csv linking EHR codes to UMLS CUIs.

    Each EHR source (conditions / medications / careplans) is processed with
    its own semantic-type bucket, so e.g. a medication description can never
    be mapped to a condition CUI like "High risk of" (T033).
    """
    per_source: list[pd.DataFrame] = []

    for csv_name, system, target_label in EHR_SOURCES:
        df = _load_ehr_source(import_dir, csv_name, system, target_label)
        if target_label == "Procedure":
            # bridge only allow-listed procedure codes (avoids untargeted noise)
            df = df[df["code"].astype(str).isin(PROCEDURE_ALLOWLIST)].reset_index(drop=True)
        print(f"  {csv_name}: {len(df):,} unique codes (target={target_label})")

        if dry_run:
            df["umls_cui"]   = None
            df["umls_name"]  = None
            df["umls_score"] = None
        else:
            allowed_tuis = SEMANTIC_TYPES[target_label]
            # For Medication, simplify "Acetaminophen 160 MG Tablet" -> "Acetaminophen"
            # so the linker hits the T121 substance CUI (which is what PubMed
            # abstracts mention) instead of a T200 clinical-drug formulation CUI.
            if target_label == "Medication":
                lookup_inputs = [_simplify_rxnorm(d) for d in df["description"].tolist()]
            else:
                lookup_inputs = df["description"].tolist()
            print(f"    Linking {len(lookup_inputs)} {target_label} descriptions...")
            matches = lookup_umls_batch(lookup_inputs, allowed_tuis, nlp, linker)
            # Manual overrides win over the linker, bypassing the TUI filter for
            # known semantic-type gaps (see MANUAL_CUI).
            n_over = 0
            for idx, code in enumerate(df["code"].tolist()):
                hit = MANUAL_CUI.get((system, str(code)))
                if hit is not None:
                    matches[idx] = {"umls_cui": hit[0], "umls_name": hit[1], "umls_score": 1.0}
                    n_over += 1
            if n_over:
                print(f"    Applied {n_over} manual CUI override(s)")
            df["umls_cui"]   = [m["umls_cui"]   if m else None for m in matches]
            df["umls_name"]  = [m["umls_name"]  if m else None for m in matches]
            df["umls_score"] = [m["umls_score"] if m else None for m in matches]
            hit = df["umls_cui"].notna().sum()
            print(f"    Matched: {hit}/{len(df)} ({hit/len(df):.1%})")

        per_source.append(df)

    # Keep one row per (code, target_label) — a SNOMED code used both as a
    # Condition and a CarePlan would survive as two rows pointing to two targets.
    combined = (
        pd.concat(per_source)
        .drop_duplicates(subset=["code", "target_label"])
        .reset_index(drop=True)
    )
    print(f"  Total rows: {len(combined):,}")

    if not dry_run:
        total_matched = combined["umls_cui"].notna().sum()
        print(f"  Overall match rate: {total_matched}/{len(combined)} "
              f"({total_matched/len(combined):.1%})")

    combined.to_csv(out_dir / "ehr_umls_mapping.csv", index=False)
    print(f"  ehr_umls_mapping.csv   -- {len(combined):,} rows")


# ── main ───────────────────────────────────────────────────────────────────────

def main(dry_run: bool, ehr_only: bool) -> None:
    print("=== snomed_umls_bridge.py ===\n")

    if not ehr_only and not LITERATURE_ENTITIES.exists():
        raise FileNotFoundError(f"Missing: {LITERATURE_ENTITIES}")
    if not NEO4J_IMPORT.exists():
        raise FileNotFoundError(f"Neo4j import folder not found: {NEO4J_IMPORT}")

    # ── literature CSVs (no ML needed) ──
    if ehr_only:
        print("-- EHR-only mode: skipping literature CSVs --")
    else:
        print("-- Literature CSVs --")
        entities = pd.read_csv(LITERATURE_ENTITIES)
        print(f"  Loaded {len(entities):,} rows from {LITERATURE_ENTITIES}")
        generate_literature_csvs(entities, NEO4J_IMPORT)

    # ── EHR mapping ──
    print("\n-- EHR UMLS mapping --")
    nlp, linker = (None, None)
    if not dry_run:
        print(f"Loading {MODEL} + UMLS linker...")
        nlp, linker = build_nlp()
        print("  Models loaded.")

    generate_ehr_mapping(NEO4J_IMPORT, NEO4J_IMPORT, nlp, linker, dry_run)

    print("\nDone. Files written directly to the Neo4j import folder.")
    print("Next: run literature_kg.cypher in Neo4j Browser.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--dry-run", action="store_true",
        help="Generate literature CSVs only; skip the slow UMLS linker step.",
    )
    p.add_argument(
        "--ehr-only", action="store_true",
        help="Regenerate ehr_umls_mapping.csv only; skip literature CSVs and their input file.",
    )
    args = p.parse_args()
    main(args.dry_run, args.ehr_only)
