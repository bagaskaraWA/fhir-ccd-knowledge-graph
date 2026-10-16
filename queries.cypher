// Synthea FHIR graph -- exploration queries
//
// Model:
//   (:Resource:<Type> {uid, ...scalars})
//     -[:SUBJECT]->(:Patient)  -[:ENCOUNTER]->(:Encounter)
//     -[:CODE|CATEGORY|VALUE|...]->(:Code {system, code, display})
//     -[:COMPONENT]->(:Component {valueQuantity_value, ...})-[:CODE]->(:Code)
//
// Code systems: http://snomed.info/sct | http://loinc.org
//               http://www.nlm.nih.gov/research/umls/rxnorm | http://hl7.org/fhir/sid/cvx


// ---------------------------------------------------------------- verification

// Node counts by resource type. Expect 149,078 total, Observation 81,748.
MATCH (r:Resource)
RETURN [l IN labels(r) WHERE l <> 'Resource'][0] AS type, count(*) AS n
ORDER BY n DESC;

// Expect 1,272 -- and no http://unitsofmeasure.org (units stay properties).
MATCH (c:Code) RETURN c.system, count(*) AS n ORDER BY n DESC;

// Every Observation reaches a Patient. Expect 0.
MATCH (o:Observation) WHERE NOT (o)-[:SUBJECT]->(:Patient) RETURN count(o) AS orphans;

// Conditional references resolved -- if this is 0, Practitioner edges silently failed.
MATCH (:Encounter)-[:PARTICIPANT_INDIVIDUAL]->(p:Practitioner) RETURN count(*) AS n;


// ------------------------------------------------------------- patient journey

// One patient's full timeline across every clinical resource type.
MATCH (p:Patient {name_family: 'Walker122'})<-[:SUBJECT]-(e:Encounter)
MATCH (x)-[:ENCOUNTER]->(e)
RETURN e.period_start AS when,
       [l IN labels(x) WHERE l <> 'Resource'][0] AS what,
       x.fhir_id AS id
ORDER BY when
LIMIT 50;

// Encounter with its provider, organization, and place -- all three arrive via
// conditional references, so this is the payoff for resolving them.
MATCH (e:Encounter)-[:SUBJECT]->(p:Patient)
MATCH (e)-[:PARTICIPANT_INDIVIDUAL]->(doc:Practitioner)
MATCH (e)-[:SERVICE_PROVIDER]->(org:Organization)
OPTIONAL MATCH (e)-[:LOCATION]->(loc:Location)
RETURN p.name_family, e.period_start, doc.name_family, org.name, loc.name
LIMIT 25;


// -------------------------------------------------------------------- cohorts

// Most common conditions by patient count.
MATCH (p:Patient)<-[:SUBJECT]-(:Condition)-[:CODE]->(c:Code)
WHERE c.system = 'http://snomed.info/sct'
RETURN c.display AS condition, count(DISTINCT p) AS patients
ORDER BY patients DESC LIMIT 20;

// Patients with a given condition -- traversal, not a property scan.
// This is why codes are shared nodes.
// Synthea displays carry SNOMED suffixes: 'Gingivitis (disorder)',
// 'Stress (finding)', 'Medication review due (situation)'.
MATCH (c:Code {display: 'Gingivitis (disorder)'})<-[:CODE]-(:Condition)-[:SUBJECT]->(p:Patient)
RETURN p.name_family, p.name_given, p.gender, p.birthDate LIMIT 25;

// Condition co-occurrence: which diagnoses travel together?
MATCH (a:Code)<-[:CODE]-(:Condition)-[:SUBJECT]->(p:Patient)
MATCH (p)<-[:SUBJECT]-(:Condition)-[:CODE]->(b:Code)
WHERE a.system = 'http://snomed.info/sct' AND b.system = 'http://snomed.info/sct'
  AND elementId(a) < elementId(b)
WITH a, b, count(DISTINCT p) AS shared
WHERE shared > 5
RETURN a.display, b.display, shared ORDER BY shared DESC LIMIT 20;


// ------------------------------------------------------------------ measures

// A LOINC observation trended over time for one patient.
MATCH (p:Patient)<-[:SUBJECT]-(o:Observation)-[:CODE]->(c:Code {code: '8302-2'})
RETURN p.name_family, o.effectiveDateTime AS t,
       o.valueQuantity_value AS value, o.valueQuantity_unit AS unit
ORDER BY p.name_family, t LIMIT 40;

// Most-recorded measurements across the cohort.
MATCH (:Observation)-[:CODE]->(c:Code)
WHERE c.system = 'http://loinc.org'
RETURN c.code, c.display, count(*) AS n ORDER BY n DESC LIMIT 20;

// Blood pressure. Systolic and diastolic are two components of ONE Observation,
// which is why components are their own nodes -- flattening them onto the parent
// keeps only the first and silently loses the other reading.
// Scope to BP panels: PRAPARE surveys are also multi-component, but their
// components carry valueCodeableConcept rather than a number, so an unscoped
// match returns null/null rows for them.
MATCH (o:Observation)-[:CODE]->(:Code {code: '85354-9'})
MATCH (o)-[:SUBJECT]->(p:Patient)
MATCH (o)-[:COMPONENT]->(c:Component)-[:CODE]->(code:Code)
WITH p, o, code.display AS measure, c.valueQuantity_value AS v
RETURN p.name_family AS patient, o.effectiveDateTime AS t,
       max(CASE WHEN measure STARTS WITH 'Systolic' THEN v END) AS systolic,
       max(CASE WHEN measure STARTS WITH 'Diastolic' THEN v END) AS diastolic
ORDER BY t DESC LIMIT 20;

// Hypertensive readings (systolic >= 140) across the cohort.
MATCH (p:Patient)<-[:SUBJECT]-(o:Observation)-[:COMPONENT]->(c:Component)-[:CODE]->(:Code {display: 'Systolic Blood Pressure'})
WHERE c.valueQuantity_value >= 140
RETURN p.name_family, count(*) AS high_readings, max(c.valueQuantity_value) AS peak
ORDER BY high_readings DESC LIMIT 15;

// Medications by RxNorm, ranked by distinct patients.
// FHIR medication[x] is a choice type, so medicationCodeableConcept and
// medicationReference both land on [:MEDICATION] -- the target label separates
// the inline code from a linked Medication resource.
MATCH (p:Patient)<-[:SUBJECT]-(:MedicationRequest)-[:MEDICATION]->(c:Code)
WHERE c.system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
RETURN c.display AS drug, count(DISTINCT p) AS patients
ORDER BY patients DESC LIMIT 20;

// The other side of that choice type: requests linked to a Medication resource.
MATCH (:MedicationRequest)-[:MEDICATION]->(m:Medication)-[:CODE]->(c:Code)
RETURN c.display AS drug, count(*) AS requests ORDER BY requests DESC LIMIT 10;


// ------------------------------------------------------------ provider network

// Practitioners connected by shared patients -- a projection FHIR never states
// directly, and the reason this data is worth putting in a graph.
MATCH (a:Practitioner)<-[:PARTICIPANT_INDIVIDUAL]-(:Encounter)-[:SUBJECT]->(p:Patient)
MATCH (p)<-[:SUBJECT]-(:Encounter)-[:PARTICIPANT_INDIVIDUAL]->(b:Practitioner)
WHERE elementId(a) < elementId(b)
WITH a, b, count(DISTINCT p) AS shared_patients
WHERE shared_patients > 1
RETURN a.name_family, b.name_family, shared_patients
ORDER BY shared_patients DESC LIMIT 20;

// Busiest organizations.
MATCH (e:Encounter)-[:SERVICE_PROVIDER]->(o:Organization)
RETURN o.name, o.address_city, count(e) AS encounters
ORDER BY encounters DESC LIMIT 15;

// Shortest path between two patients through shared providers.
MATCH (a:Patient), (b:Patient)
WHERE a.name_family = 'Walker122' AND b.name_family <> a.name_family
MATCH path = shortestPath((a)-[*..6]-(b))
RETURN [n IN nodes(path) | [l IN labels(n) WHERE l <> 'Resource'][0]] AS hops
LIMIT 5;
