// literature_kg.cypher
// -------------------------
// FHIR-native port of literature_kg.cypher for the `sihdfhir` database.
// Run with :use sihdfhir. Reads abstracts.csv / concepts.csv /
// abstract_concept_edges.csv from the cobafhirlagi import folder.
//
// WHAT CHANGED vs the thesis version:
//   1. The four SAME_CONCEPT blocks are OMITTED -- ehr_concept_kg.cypher
//      already created (:Concept)-[:SAME_CONCEPT]->(:Code) in Phase 1, and the
//      literature-only Concepts loaded here have no EHR bridge by definition.
//   2. CO_OCCURS_IN_LITERATURE is materialized between :Code nodes, NOT between
//      per-occurrence :Medication/:Condition resource nodes (which would multiply
//      per patient -- 70k med / 131k condition nodes). The med/condition sides are
//      picked out by the SAME_CONCEPT edge's `targetLabel` property (set in Phase 1),
//      which is exactly the thesis's Medication-vs-Condition distinction.
//
// Abstract/Concept/MENTIONS loads are UNCHANGED (they never touch resource nodes).

// ── CONSTRAINTS ────────────────────────────────────────────────────────────────
CREATE CONSTRAINT `pmid_Abstract_key` IF NOT EXISTS
FOR (n: `Abstract`) REQUIRE (n.`pmid`) IS NODE KEY;

CREATE CONSTRAINT `umlsCui_Concept_key` IF NOT EXISTS
FOR (n: `Concept`) REQUIRE (n.`umlsCui`) IS NODE KEY;

// ── Abstract nodes ─────────────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///abstracts.csv' AS row
WITH row WHERE NOT row.`pmid` IS NULL
CALL (row) {
  MERGE (n: `Abstract` { `pmid`: toInteger(row.`pmid`) })
  SET n.`pmid` = toInteger(row.`pmid`)
} IN TRANSACTIONS OF 10000 ROWS;

// ── Concept nodes (MERGE onto the EHR/stub concepts by umlsCui) ────────────────
LOAD CSV WITH HEADERS FROM 'file:///concepts.csv' AS row
WITH row WHERE NOT row.`umls_cui` IS NULL
CALL (row) {
  MERGE (n: `Concept` { `umlsCui`: row.`umls_cui` })
  SET n.`umlsCui`   = row.`umls_cui`
  SET n.`umlsName`  = row.`umls_name`
  SET n.`umlsTypes` = row.`umls_types`
  SET n.`meshName`  = row.`mesh_name`
} IN TRANSACTIONS OF 10000 ROWS;

// ── Abstract -[MENTIONS]-> Concept ─────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///abstract_concept_edges.csv' AS row
WITH row WHERE NOT row.`pmid` IS NULL AND NOT row.`umls_cui` IS NULL
CALL (row) {
  MATCH (a: `Abstract` { `pmid`: toInteger(row.`pmid`) })
  MATCH (c: `Concept`  { `umlsCui`: row.`umls_cui` })
  MERGE (a)-[r: `MENTIONS`]->(c)
  SET r.`category`     = row.`category`
  SET r.`mentionCount` = toInteger(row.`mention_count`)
} IN TRANSACTIONS OF 10000 ROWS;

// SAME_CONCEPT -> :Code already exists from ehr_concept_kg.cypher (Phase 1).

// ── (optional) scrub before re-materializing CO_OCCURS ─────────────────────────
// MATCH (:Code)-[r: `CO_OCCURS_IN_LITERATURE`]->(:Code) DELETE r;

// ── CO_OCCURS_IN_LITERATURE materialization (between :Code nodes) ───────────────
// (:Code med)-[:CO_OCCURS_IN_LITERATURE]->(:Code cond), derived from Abstract
// co-mentions via the Concept layer. med side = SAME_CONCEPT{targetLabel:'Medication'},
// cond side = SAME_CONCEPT{targetLabel:'Condition'} -- the thesis's Med/Cond split.

// Step 1: per medication-code document frequency.
MATCH (medk: `Code`)
WHERE EXISTS { (: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Medication' }]->(medk) }
OPTIONAL MATCH (a: `Abstract`)-[: `MENTIONS`]->(: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Medication' }]->(medk)
WITH medk, count(DISTINCT a) AS df
SET medk.`_litDf` = df;

// Step 2: per condition-code document frequency.
MATCH (condk: `Code`)
WHERE EXISTS { (: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Condition' }]->(condk) }
OPTIONAL MATCH (a: `Abstract`)-[: `MENTIONS`]->(: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Condition' }]->(condk)
WITH condk, count(DISTINCT a) AS df
SET condk.`_litDf` = df;

// Step 3: total abstract count N on a singleton sentinel.
MATCH (a: `Abstract`)
WITH count(a) AS N
MERGE (s: `_LiteratureStats` { `id`: 'singleton' })
SET s.`N` = N;

// Step 4: materialize the co-occurrence edges.
MATCH (s: `_LiteratureStats` { `id`: 'singleton' })
WITH s.`N` AS N
MATCH (a: `Abstract`)-[mm: `MENTIONS`]->(: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Medication' }]->(medk: `Code`)
MATCH (a)-[cm: `MENTIONS`]->(: `Concept`)-[: `SAME_CONCEPT` { `targetLabel`: 'Condition' }]->(condk: `Code`)
WHERE medk.`_litDf` > 0 AND condk.`_litDf` > 0
WITH N, medk, condk,
     count(DISTINCT a) AS articleCount,
     sum(CASE WHEN mm.`mentionCount` < cm.`mentionCount`
              THEN mm.`mentionCount` ELSE cm.`mentionCount` END) AS weightedCoMentions
WITH medk, condk, articleCount, weightedCoMentions,
     log10(toFloat(articleCount) * N / (medk.`_litDf` * condk.`_litDf`)) AS pmi
MERGE (medk)-[r: `CO_OCCURS_IN_LITERATURE`]->(condk)
SET r.`articleCount`       = articleCount,
    r.`weightedCoMentions` = weightedCoMentions,
    r.`pmi`                = pmi;

// Step 5: cleanup temp state.
MATCH (k: `Code`) WHERE k.`_litDf` IS NOT NULL REMOVE k.`_litDf`;
MATCH (s: `_LiteratureStats`) DELETE s;
