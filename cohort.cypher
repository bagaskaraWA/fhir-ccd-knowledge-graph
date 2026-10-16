// ============================================================================
// Pooled SIHD cohort definition -- FHIR-native graph (database: sihdfhir)
//
// The cohort is defined by a CLINICAL CRITERION, source-agnostic: a patient is
// in the SIHD cohort iff their record carries a CCD-defining SNOMED code --
// regardless of which Synthea run generated them (2k "SIHD-guaranteed" vs 3k
// general). Rationale:
//   * Generation provenance is not a clinical variable and has no real-world
//     analog -- a real cohort study selects on diagnosis codes, not on which
//     simulation produced a patient.
//   * The graph cannot tell the two sources apart anyway (both code IHD as
//     414545008), and the CRS / gold oracle never see provenance.
//   * The clinical criterion SELF-CLEANS: the ~1,730 empty stubs from the SIHD
//     run have no condition code, so they fall out automatically -- no manual
//     exclusion rule needed.
//
// Verified reference values (database sihdfhir, this build):
//   cohort           = 943 patients
//   composition      = 355 bare (0 comorbidities) / 588 rich (>=1)
//   in-cohort comorb = 537 diabetes, 373 hypertension, 193 CKD
//
// Report the bare/rich split in Methods so the aggregate P/R/F1 is understood
// as blending two clinical profiles. Stratify (if at all) on comorbidity
// burden -- the honest clinical variable -- never on generation source.
// ============================================================================


// ---------------------------------------------------- CCD-defining code set
//
// Canonical set for THIS Synthea cohort (7 SNOMED codes). Inlined in each query
// below because Neo4j Browser runs statements independently (no shared vars).
//
//   414545008  Ischemic heart disease (disorder)              876
//   399261000  History of coronary artery bypass grafting     385
//   399211009  History of myocardial infarction               167
//   22298006   Myocardial infarction (disorder)                90
//   401314000  Acute NSTEMI                                     89
//   401303003  Acute STEMI                                      69
//   4557003    Preinfarction syndrome (unstable angina)          9
//
// Deliberately EXCLUDED:
//   274531002  Abnormal cardiac-imaging FINDING (879 pts) -- a finding, not a
//              diagnosis; adding it changes the count by 0 (all its patients
//              already carry a disorder code above).
//
// Clinically valid but NOT emitted by this Synthea build (confirmed absent) --
// listed so the criterion reads as clinically complete but data-limited:
//   413838009  Chronic ischemic heart disease
//   53741008   Coronary arteriosclerosis
//   194828000  Angina


// ------------------------------------------------------------- 1. cohort size
// -> 943
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006',
                 '401314000','401303003','4557003']
RETURN count(DISTINCT p) AS sihdCohort;


// ------------------------------------------------ 2. breakdown by defining code
// A patient may carry several; columns are not mutually exclusive.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006',
                 '401314000','401303003','4557003']
RETURN k.code AS code, k.display AS diagnosis, count(DISTINCT p) AS patients
ORDER BY patients DESC;


// ---------------------------------------------- 3. comorbidity distribution
// Within the SIHD cohort. 'diabet' excludes prediabetes; CKD via "chronic kidney".
// Run each individually. -> diabetes 537 | hypertension 373 | CKD 193
// diabetes:
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006','401314000','401303003','4557003']
WITH DISTINCT p
MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
WHERE c.display =~ '(?i).*diabet.*' AND NOT c.display =~ '(?i).*predi.*'
RETURN count(DISTINCT p) AS withDiabetes;   // -> 537
// hypertension:
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006','401314000','401303003','4557003']
WITH DISTINCT p
MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
WHERE c.display =~ '(?i).*hypertension.*'
RETURN count(DISTINCT p) AS withHypertension;   // -> 373
// chronic kidney disease:
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006','401314000','401303003','4557003']
WITH DISTINCT p
MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
WHERE c.display =~ '(?i).*chronic kidney.*'
RETURN count(DISTINCT p) AS withCKD;   // -> 193


// -------------------------------------------- 4. heterogeneity split (Methods)
// bare = 0 of {diabetes, hypertension, CKD}; rich = >=1. The composition-
// disclosure number: report so aggregate metrics are read as a blend.
// -> bare 355 | rich 588
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006',
                 '401314000','401303003','4557003']
WITH DISTINCT p
OPTIONAL MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
  WHERE c.display =~ '(?i).*(diabet|hypertension|chronic kidney).*'
WITH p, count(c) AS comorbidities
RETURN sum(CASE WHEN comorbidities = 0 THEN 1 ELSE 0 END) AS bare,
       sum(CASE WHEN comorbidities > 0 THEN 1 ELSE 0 END) AS rich;


// --------------------------------------- 5. per-patient comorbidity count
// For stratified reporting and for feeding pick_review_patients.py (choose
// review examples by clinical richness, never by generation source).
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006',
                 '401314000','401303003','4557003']
WITH DISTINCT p
OPTIONAL MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
  WHERE c.display =~ '(?i).*(diabet|hypertension|chronic kidney).*'
RETURN p.uid AS patient, count(DISTINCT c) AS comorbidityCount
ORDER BY comorbidityCount DESC;


// ------------------------------------------------- 6. cohort UID export
// The 943 cohort patient UIDs -- the hand-off to downstream selection/labelling.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
WHERE k.code IN ['414545008','399261000','399211009','22298006',
                 '401314000','401303003','4557003']
RETURN DISTINCT p.uid AS patient
ORDER BY patient;
