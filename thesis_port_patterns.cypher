// ============================================================================
// Thesis CRS query patterns, ported to the FHIR-native EHR graph
//
// Each block pairs the thesis pattern (Synthea CSV graph) with its FHIR
// equivalent. All FHIR blocks are VERIFIED against the 115-patient
// cobafhirlagi graph; counts in comments are from that run.
//
// Gate/AND/targetLogic SEMANTICS ARE UNCHANGED -- only the graph pattern moves.
// See thesis'_CLAUDE.md "CRS query layer" for the semantics that still apply.
// ============================================================================


// ---------------------------------------------------------------- traversals
//
// The thesis keys Condition/Medication on `code` (one node per SNOMED/RxNorm
// code). The FHIR graph keys resources per-occurrence and hoists codes into
// shared (:Code {system, code}) nodes -- which are the SAME semantic object as
// the thesis's code-keyed nodes. So :Code is the bridge anchor, and the three
// SAME_CONCEPT blocks collapse into one.

// THESIS: (p:Patient)-[:HAS_CONDITION]->(c:Condition {code})
// FHIR:
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code {code: '414545008'})
RETURN count(DISTINCT p) AS ccdPatients;                      // -> 19

// THESIS: (p)-[:HAS]->(m:Medication {code})
// FHIR: medication[x] is a CHOICE TYPE -- [:MEDICATION] lands on :Code (inline)
// OR :Medication (linked resource). Match :Code explicitly or you silently
// halve the drug edges.
MATCH (p:Patient)<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(k:Code)
WHERE k.system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
RETURN count(DISTINCT p) AS pts, count(DISTINCT k) AS drugs;

// THESIS: (p)-[:UNDERWENT]->(:Procedure {code})
// FHIR: same finding-vs-act problem -- PCI is still a procedure EVENT here, so
// the PROCEDURE_ALLOWLIST + MANUAL_CUI alias (PCI -> C1320647 History of PCI)
// is still required, unchanged.
MATCH (p:Patient)<-[:SUBJECT]-(:Procedure)-[:CODE]->(k:Code {code: '415070008'})
RETURN count(DISTINCT p) AS pciPatients;


// ------------------------------------------------------- full gate+AND spine
//
// THESIS:
//   (p:Patient)-[:HAS_CONDITION]->(:Condition)<-[:SAME_CONCEPT]-(:Concept)
//     <-[:TARGETS]-(rec:Recommendation)
// FHIR (one extra hop, direction reversed):

MATCH (p:Patient {uid: $pid})<-[:SUBJECT]-(:Condition)-[:CODE]->(k:Code)
      <-[:SAME_CONCEPT]-(concept:Concept)<-[:TARGETS]-(rec:Recommendation)
WHERE concept.umlsCui <> 'C0151744'          // the anchor is a GATE, not a filter
RETURN rec.recId, collect(DISTINCT concept.umlsCui) AS matchedExtraConds;
// Then apply the unchanged rule:
//   fire when size(extraConds)=0
//        OR (coalesce(rec.targetLogic,'AND')='OR'  AND size(matched)>=1)
//        OR (coalesce(rec.targetLogic,'AND')='AND' AND size(matched)=size(extraConds))


// ------------------------------------------------------- observation gating
//
// The thesis calls this "bridge observations". IT IS NOT A BRIDGE.
// BMI>=30 and LVEF<=40 are NUMERIC gates -- no UMLS CUI is involved. They only
// ever needed observations as queryable nodes, which is a LOADING problem.
// This is the single biggest win of the port.

// WM:2/3 -- obesity. Currently a structural FN (BMI never reaches Neo4j).
// Rulebook rule 4: "worst-ever" aggregation -> max().
// VERIFIED: of 19 CCD patients, 6 obese / 13 not / 0 unknown -> DISCRIMINATES.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code {code: '414545008'})
WITH DISTINCT p
OPTIONAL MATCH (p)<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {code: '39156-5'})
WITH p, max(o.valueQuantity_value) AS worstBmi
RETURN p.name_family, worstBmi, worstBmi >= 30 AS obese
ORDER BY worstBmi DESC;

// NOTE: 39156-5 = BMI [Ratio]; 59576-9 = BMI [Percentile] (0-100).
// These are DISTINCT :Code nodes -- the exact bug silver_oracle.py's validation
// caught by substring-matching observation names. Exact code match makes that
// bug class structurally impossible. Same for statin<->nystatin (match RxNorm
// code, not name) and the LDL naming ("Cholesterol in LDL...", not "low density
// lipoprotein").

// LIPID:5 -- LDL. Rule 3: can't confirm -> 0, so IS NULL must stay excluded.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code {code: '414545008'})
WITH DISTINCT p
OPTIONAL MATCH (p)<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {code: '18262-6'})
WITH p, max(o.valueQuantity_value) AS maxLdl
WHERE maxLdl IS NOT NULL AND maxLdl >= 70
RETURN count(*) AS ldlPts;

// BB:1/2, SGLT2:4/6 -- LVEF. Rule 3: unknown LVEF -> 0 for BOTH <=40 and >40;
// never infer "normal".
// CAUTION: Synthea emits NON-PHYSIOLOGICAL LVEF -- reproduced here at max
// 89.28% (impossible; normal ~55-70). This is a GENERATOR artifact, confirmed
// independent of the CSV exporter. pick_review_patients.py screening still
// applies. Also thin: only 5/115 patients have any LVEF at all -- an
// observation COVERAGE ceiling, distinct from the loading gap this fixes.
MATCH (p:Patient)<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {code: '10230-1'})
WITH p, min(o.valueQuantity_value) AS worstLvef
RETURN p.name_family, worstLvef, worstLvef <= 40 AS reducedEf;

// Blood pressure -- needs the COMPONENT hop. Systolic and diastolic are two
// components of ONE Observation; that is why :Component nodes exist.
// Rulebook rule 4 EXCEPTION: BP and smoking use MOST-RECENT, not worst-ever.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(:Code {code: '414545008'})
WITH DISTINCT p
MATCH (p)<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {code: '85354-9'})
WITH p, o ORDER BY o.effectiveDateTime DESC
WITH p, head(collect(o)) AS latest
MATCH (latest)-[:COMPONENT]->(c:Component)-[:CODE]->(cc:Code)
WITH p, latest.effectiveDateTime AS t,
     max(CASE WHEN cc.display STARTS WITH 'Systolic'  THEN c.valueQuantity_value END) AS systolic,
     max(CASE WHEN cc.display STARTS WITH 'Diastolic' THEN c.valueQuantity_value END) AS diastolic
RETURN p.name_family, t, systolic, diastolic
ORDER BY systolic DESC;

// Smoking -- most-recent (status cycles Never -> Daily -> Ex over time).
MATCH (p:Patient)<-[:SUBJECT]-(o:Observation)-[:CODE]->(:Code {code: '72166-2'})
WITH p, o ORDER BY o.effectiveDateTime DESC
WITH p, head(collect(o)) AS latest
MATCH (latest)-[:VALUE]->(v:Code)
RETURN v.display AS smokingStatus, count(*) AS pts ORDER BY pts DESC;


// ------------------------------------------------------------ bridge sanity
//
// Run these AFTER the Concept layer is minted against :Code.

// The cohort gate must bridge, or the whole CRS is broken.
MATCH (:Concept {umlsCui: 'C0151744'})-[:SAME_CONCEPT]->(k:Code)
RETURN k.system, k.code, k.display;

// Source for ehr_umls_mapping.csv -- replaces the EHR_SOURCES CSV walk in
// snomed_umls_bridge.py --ehr-only. The graph already deduplicated the codes.
// Only 2 of 1,272 codes are used by >1 resource type, so srcType (-> the TUI
// bucket / target_label) is well-defined.
MATCH (r:Resource)-[:CODE]->(k:Code)
WITH k, collect(DISTINCT [l IN labels(r) WHERE l <> 'Resource'][0])[0] AS srcType
RETURN k.system AS system_uri, k.code AS code, k.display AS description, srcType
ORDER BY srcType, k.code;
// Map system_uri -> the thesis's system string before writing the CSV:
//   http://snomed.info/sct                        -> SNOMED-CT
//   http://www.nlm.nih.gov/research/umls/rxnorm   -> RxNorm
//   http://hl7.org/fhir/sid/cvx                   -> CVX
//   http://loinc.org                              -> LOINC   (new: observations)
// _simplify_rxnorm and _strip_snomed_tag are STILL REQUIRED -- FHIR displays
// carry the same "(disorder)" tags and full "<drug> <strength> <form>" strings.
