// guideline_kg.cypher
// -------------------
// Loads the clinical guidance layer: the 2023 AHA/ACC/ACCP/ASPC/NLA/PCNA
// Guideline for the Management of Patients With Chronic Coronary Disease
// (Virani et al., JACC 2023; DOI 10.1016/j.jacc.2023.04.003).
//
// RUN ORDER: after synthea.cypher AND literature_kg.cypher. This script needs
// Concept nodes and SAME_CONCEPT edges (so RECOMMENDS/CONTRAINDICATES/TARGETS
// can traverse to EHR nodes) and Abstract nodes (for CITES) to already exist.
//
// Input CSVs (place in the Neo4j import folder):
//   guideline_recommendations.csv  -- one row per curated recommendation (required)
//   guideline_concepts.csv         -- Concepts the literature layer didn't supply (optional)
//   guideline_citations.csv        -- resolved recommendation->PMID pairs (optional, exploratory)
//
// Schema added:
//   (:Guideline {guidelineId, title, year, organization, doi, pmid, loeScheme, url})
//   (:Recommendation {recommendationId, sectionTitle, recNumber, cor, loe, text, interventionType, targetLogic})
//   (:Guideline)-[:CONTAINS]->(:Recommendation)
//   (:Recommendation)-[:RECOMMENDS]->(:Concept)       -- COR 1 / 2a / 2b  (positive)
//   (:Recommendation)-[:CONTRAINDICATES]->(:Concept)  -- COR 3-Harm / 3-NoBenefit (negative)
//   (:Recommendation)-[:TARGETS]->(:Concept)          -- the condition the rec applies to
//   (:Recommendation)-[:CITES]->(:Abstract)           -- exploratory; supporting evidence
//
//   The Concept layer then bridges to the EHR via the existing SAME_CONCEPT edges:
//     Recommendation -> Concept -> SAME_CONCEPT -> Medication | CarePlan | Condition
//
// COR encoding in the CSV (no colon/space -- clean tokens for property values):
//   1, 2a, 2b      -> positive  -> RECOMMENDS edge
//   3-NoBenefit    -> negative  -> CONTRAINDICATES edge
//   3-Harm         -> negative  -> CONTRAINDICATES edge
// The RECOMMENDS vs CONTRAINDICATES split is DERIVED here from `cor`, so the
// curator never names the edge type -- just records the COR shown in the guideline.
//
// LOE encoding (2015+ ACC/AHA scheme, used verbatim by this guideline):
//   A, B-R, B-NR, C-LD, C-EO
//
// intervention_type encoding (drives downstream filtering, not edge type):
//   Medication   -- pharmacologic intervention only
//   CarePlan     -- lifestyle / procedural / counseling intervention only
//   Mixed        -- single guideline rec covering BOTH; split into two CSV rows
//                   with `:a` / `:b` suffixes on recommendation_id, one row per
//                   intervention_type, sharing section_title / rec_number / cor /
//                   loe / text / condition_cuis / cited_ref_numbers.
//
// Class-level recommendations (e.g. "statin therapy", "beta blocker"): list the
// specific member-drug CUIs that exist in the Concept layer, NOT the class CUI.
// A class CUI typically dead-ends (no SAME_CONCEPT from class Concept to any
// Medication node). Source the members from the graph itself:
//   MATCH (c:Concept)-[:SAME_CONCEPT]->(m:Medication)
//   WHERE toLower(m.descriptionName) CONTAINS 'statin'
//   RETURN DISTINCT c.umlsCui, c.umlsName, m.descriptionName ORDER BY c.umlsName;

// ── CONSTRAINTS ────────────────────────────────────────────────────────────────

CREATE CONSTRAINT `guidelineId_Guideline_key` IF NOT EXISTS
FOR (n: `Guideline`)
REQUIRE (n.`guidelineId`) IS NODE KEY;

CREATE CONSTRAINT `recommendationId_Recommendation_key` IF NOT EXISTS
FOR (n: `Recommendation`)
REQUIRE (n.`recommendationId`) IS NODE KEY;

// ── GUIDELINE node ─────────────────────────────────────────────────────────────
// Single node -- hardcoded MERGE rather than a one-row CSV.
// TODO: verify the PMID on PubMed and uncomment the `g.pmid = ...` line below.
// (Setting a property to literal null in Cypher REMOVES it -- so a placeholder
// `pmid = null` does nothing; leave the line commented until the real value is in.)

MERGE (g: `Guideline` { `guidelineId`: 'CCD-2023' })
SET g.`title`        = '2023 AHA/ACC/ACCP/ASPC/NLA/PCNA Guideline for the Management of Patients With Chronic Coronary Disease',
    g.`year`         = 2023,
    g.`organization` = 'AHA/ACC/ACCP/ASPC/NLA/PCNA',
    g.`doi`          = '10.1016/j.jacc.2023.04.003',
    // g.`pmid`      = 0000000,                              -- TODO: fill in verified PMID
    g.`loeScheme`    = 'ACC/AHA-2015+',
    g.`url`          = 'https://doi.org/10.1016/j.jacc.2023.04.003';

// ── RECOMMENDATION nodes ───────────────────────────────────────────────────────

LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
WITH row
WHERE NOT row.`recommendation_id` IS NULL AND trim(row.`recommendation_id`) <> ''
CALL (row) {
  MERGE (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
  SET rec.`sectionTitle`     = row.`section_title`,
      rec.`recNumber`        = toInteger(row.`rec_number`),
      rec.`cor`              = row.`cor`,
      rec.`loe`              = row.`loe`,
      rec.`text`             = row.`text`,
      rec.`interventionType` = row.`intervention_type`
} IN TRANSACTIONS OF 1000 ROWS;

// ── targetLogic : disjunctive-target recs ──────────────────────────────────────
// A few recs list their TARGETS as ALTERNATIVES (OR), not conjunctive preconditions
// (AND): CR:1:1 "after MI, PCI, or CABG", CR:1:2 "stable angina or heart transplant",
// RAAI:1 "hypertension, diabetes, LVEF<=40, or CKD". The CRS gate+AND query branches on
// this flag (default AND), so a patient matching ANY one alternative applies. The flat
// schema can't infer it, so it is set explicitly here.
MATCH (rec: `Recommendation`)
WHERE rec.`recommendationId` IN ['CCD-2023:CR:1:1', 'CCD-2023:CR:1:2', 'CCD-2023:RAAI:1']
SET rec.`targetLogic` = 'OR';

// ── CONTAINS : Guideline -> Recommendation ─────────────────────────────────────

LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
WITH row
WHERE NOT row.`recommendation_id` IS NULL AND trim(row.`recommendation_id`) <> ''
CALL (row) {
  MATCH (g:   `Guideline`      { `guidelineId`: 'CCD-2023' })
  MATCH (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
  MERGE (g)-[:`CONTAINS`]->(rec)
} IN TRANSACTIONS OF 1000 ROWS;

// ── (optional) guideline_concepts.csv ──────────────────────────────────────────
// Use ONLY for UMLS concepts the guideline references but the PubMed literature
// layer never produced (so no Concept node exists for them yet). For concepts
// already present from literature_kg.cypher this MERGE just matches the existing
// node; SET then refreshes name/types with identical values -- harmless.
//
// LOAD CSV WITH HEADERS FROM 'file:///guideline_concepts.csv' AS row
// WITH row
// WHERE NOT row.`umls_cui` IS NULL AND trim(row.`umls_cui`) <> ''
// CALL (row) {
//   MERGE (c: `Concept` { `umlsCui`: row.`umls_cui` })
//   SET c.`umlsName`  = row.`umls_name`,
//       c.`umlsTypes` = row.`umls_types`
// } IN TRANSACTIONS OF 1000 ROWS;

// ── (optional) cleanup before re-loading edges ─────────────────────────────────
// MERGE never deletes stale edges. If you re-curate guideline_recommendations.csv,
// scrub the guideline edges first:
//   MATCH (:Recommendation)-[r:`RECOMMENDS`]->()      DELETE r;
//   MATCH (:Recommendation)-[r:`CONTRAINDICATES`]->() DELETE r;
//   MATCH (:Recommendation)-[r:`TARGETS`]->()         DELETE r;
//   MATCH (:Recommendation)-[r:`CITES`]->()           DELETE r;
// To fully reset the layer, DETACH DELETE the Recommendation nodes too.

// ── PRE-LOAD CHECK : which CSV CUIs are not yet Concept nodes? ─────────────────
// Run this BEFORE the edge blocks below. Any CUI it returns will silently produce
// zero edges (MATCH skips missing nodes). Fix by correcting the CUI in the CSV
// or adding the concept via guideline_concepts.csv.
//
// LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
// UNWIND split(coalesce(row.`target_cuis`,'') + ';' + coalesce(row.`condition_cuis`,''), ';') AS rawCui
// WITH DISTINCT trim(rawCui) AS cui
// WHERE cui <> ''
// OPTIONAL MATCH (c: `Concept` { `umlsCui`: cui })
// WITH cui, c WHERE c IS NULL
// RETURN cui AS missing_cui ORDER BY missing_cui;

// ── RECOMMENDS : Recommendation -> Concept  (COR 1 / 2a / 2b) ──────────────────
// One edge per CUI in the semicolon-separated `target_cuis` list.

LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
WITH row
WHERE NOT row.`cor` STARTS WITH '3'
  AND NOT row.`target_cuis` IS NULL
UNWIND split(row.`target_cuis`, ';') AS rawCui
WITH row, trim(rawCui) AS cui
WHERE cui <> ''
CALL (row, cui) {
  MATCH (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
  MATCH (con: `Concept`        { `umlsCui`: cui })
  MERGE (rec)-[:`RECOMMENDS`]->(con)
} IN TRANSACTIONS OF 1000 ROWS;

// ── CONTRAINDICATES : Recommendation -> Concept  (COR 3-Harm / 3-NoBenefit) ────

LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
WITH row
WHERE row.`cor` STARTS WITH '3'
  AND NOT row.`target_cuis` IS NULL
UNWIND split(row.`target_cuis`, ';') AS rawCui
WITH row, trim(rawCui) AS cui
WHERE cui <> ''
CALL (row, cui) {
  MATCH (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
  MATCH (con: `Concept`        { `umlsCui`: cui })
  MERGE (rec)-[:`CONTRAINDICATES`]->(con)
} IN TRANSACTIONS OF 1000 ROWS;

// ── TARGETS : Recommendation -> Concept  (the condition the rec is about) ──────

LOAD CSV WITH HEADERS FROM 'file:///guideline_recommendations.csv' AS row
WITH row
WHERE NOT row.`condition_cuis` IS NULL
UNWIND split(row.`condition_cuis`, ';') AS rawCui
WITH row, trim(rawCui) AS cui
WHERE cui <> ''
CALL (row, cui) {
  MATCH (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
  MATCH (con: `Concept`        { `umlsCui`: cui })
  MERGE (rec)-[:`TARGETS`]->(con)
} IN TRANSACTIONS OF 1000 ROWS;

// ── CITES : Recommendation -> Abstract  (EXPLORATORY) ──────────────────────────
// Depends on guideline_citations.csv, produced by the citation-resolver script
// (parses the guideline's per-section reference lists, resolves each reference to
// a PMID via NCBI ecitmatch with esearch fallback).
// Columns: recommendation_id, pmid, match_method, match_confidence.
//
// Abstracts cited by the guideline but absent from the SIHD corpus are created as
// stubs (pmid only) tagged source='guideline_citation', so a later NER pass can
// find and enrich them. Corpus abstracts keep whatever source the literature
// pipeline set (currently none -- consider backfilling source='sihd_corpus').
//
// LOAD CSV WITH HEADERS FROM 'file:///guideline_citations.csv' AS row
// WITH row
// WHERE NOT row.`pmid` IS NULL AND trim(row.`pmid`) <> ''
// CALL (row) {
//   MATCH (rec: `Recommendation` { `recommendationId`: row.`recommendation_id` })
//   MERGE (a: `Abstract` { `pmid`: toInteger(row.`pmid`) })
//     ON CREATE SET a.`source` = 'guideline_citation'
//   MERGE (rec)-[r:`CITES`]->(a)
//   SET r.`matchMethod`     = row.`match_method`,
//       r.`matchConfidence` = toFloat(row.`match_confidence`)
// } IN TRANSACTIONS OF 1000 ROWS;

// ── VERIFICATION ───────────────────────────────────────────────────────────────
//
// Recommendation counts by COR:
//   MATCH (r:Recommendation) RETURN r.cor AS cor, count(*) AS n ORDER BY cor;
//
// Recommendations that reach an EHR Medication (full traversal works):
//   MATCH (rec:Recommendation)-[:RECOMMENDS]->(:Concept)-[:SAME_CONCEPT]->(m:Medication)
//   RETURN rec.recommendationId, rec.cor, collect(DISTINCT m.code) AS meds;
//
// Contraindications reaching an EHR Medication (the CRS safety query):
//   MATCH (rec:Recommendation)-[:CONTRAINDICATES]->(:Concept)-[:SAME_CONCEPT]->(m:Medication)
//   RETURN rec.recommendationId, rec.text, collect(DISTINCT m.code) AS meds;
//
// Recommendations with NO outgoing RECOMMENDS/CONTRAINDICATES edge -- a curation
// gap, or every target CUI failed to resolve to a Concept:
//   MATCH (rec:Recommendation)
//   WHERE NOT (rec)-[:RECOMMENDS]->() AND NOT (rec)-[:CONTRAINDICATES]->()
//   RETURN rec.recommendationId, rec.sectionTitle, rec.cor;
