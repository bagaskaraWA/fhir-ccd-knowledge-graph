// ehr_concept_kg.cypher
// -------------------------
// FHIR-native port of ehr_concept_kg.cypher for the `sihdfhir` database.
// Run with :use sihdfhir  (LOAD CSV reads ehr_umls_mapping.csv from the
// cobafhirlagi DBMS import folder, shared by all its databases).
//
// WHAT CHANGED vs the thesis version:
//   The thesis keyed Condition/Medication/CarePlan/Procedure on `code` and had
//   FOUR SAME_CONCEPT blocks routed on target_label. In the FHIR graph the code
//   lives on a shared (:Code {system, code}) node, not on the resource -- so the
//   four blocks COLLAPSE INTO ONE targeting :Code. Downstream, the resource type
//   is recovered by which resource CODEs to that :Code, so no fidelity is lost;
//   the node-key-asymmetry (CarePlan many-nodes-per-code) workaround disappears.
//
// Concept mint blocks are UNCHANGED -- they never touched resource nodes.
//
// Prerequisites:
//   1. sihdfhir loaded (Condition/Medication/CarePlan/Procedure + :Code nodes).
//   2. ehr_umls_mapping.csv in the import folder
//      (graph_export_ehr_codes.py -> snomed_umls_bridge.py --ehr-only).

// ── CONSTRAINT ─────────────────────────────────────────────────────────────────
CREATE CONSTRAINT `umlsCui_Concept_key` IF NOT EXISTS
FOR (n: `Concept`)
REQUIRE (n.`umlsCui`) IS NODE KEY;

// ── EHR-derived Concept nodes (UNCHANGED from thesis) ──────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///ehr_umls_mapping.csv' AS row
WITH row
WHERE NOT row.`umls_cui` IS NULL AND NOT row.`umls_cui` = ''
CALL (row) {
  MERGE (c: `Concept` { `umlsCui`: row.`umls_cui` })
  ON CREATE SET c.`umlsName` = row.`umls_name`
  SET c.`inEhr` = true
} IN TRANSACTIONS OF 10000 ROWS;

// ── (optional) scrub before reload ─────────────────────────────────────────────
// Run ONCE before re-loading if ehr_umls_mapping.csv was regenerated. MERGE adds
// new edges but never deletes edges whose mapping has since changed.
//
// MATCH ()-[r: `SAME_CONCEPT`]->() DELETE r;

// ── SINGLE SAME_CONCEPT block -> :Code ─────────────────────────────────────────
// row.system is the thesis label ('SNOMED-CT' / 'RxNorm'); :Code.system is the
// FHIR URI. Translate so the match uses the (system, code) node key, and a
// SNOMED code number can never collide with an RxNorm code number.
// `targetLabel` is carried onto the edge for provenance / debugging.
LOAD CSV WITH HEADERS FROM 'file:///ehr_umls_mapping.csv' AS row
WITH row,
     CASE row.`system`
       WHEN 'SNOMED-CT' THEN 'http://snomed.info/sct'
       WHEN 'RxNorm'    THEN 'http://www.nlm.nih.gov/research/umls/rxnorm'
       WHEN 'CVX'       THEN 'http://hl7.org/fhir/sid/cvx'
       ELSE null
     END AS sysUri
WHERE NOT row.`umls_cui` IS NULL AND NOT row.`umls_cui` = '' AND NOT sysUri IS NULL
CALL (row, sysUri) {
  MATCH (c: `Concept` { `umlsCui`: row.`umls_cui` })
  MATCH (k: `Code` { `system`: sysUri, `code`: row.`code` })
  MERGE (c)-[r: `SAME_CONCEPT`]->(k)
  SET r.`matchScore`   = toFloat(row.`umls_score`)
  SET r.`sourceSystem` = row.`system`
  SET r.`targetLabel`  = row.`target_label`
} IN TRANSACTIONS OF 10000 ROWS;
