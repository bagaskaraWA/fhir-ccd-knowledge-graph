"""Export EHR codes from the FHIR-native `sihdfhir` graph into the CSVs that
snomed_umls_bridge.py already reads (`conditions.csv`, `medications.csv`,
`careplans.csv`, `procedures.csv`).

This is the FHIR replacement for the thesis's Synthea CSV inputs to the bridge.
The bridge's three-pass linker is left completely untouched: it still reads
`code` + `description` CSVs and attaches (system, target_label) from its own
EHR_SOURCES. We just source those CSVs from the graph instead of Synthea's CSV
export, so the bridge links exactly the code universe that is actually in the
graph.

Buckets mirror the thesis EHR_SOURCES (system, target_label):
  Condition  SNOMED  <- (:Condition)-[:CODE]->(:Code)
  Medication RxNorm  <- (:Code) reachable as a medication (rxnorm system)
  CarePlan   SNOMED  <- (:CarePlan)-[:CATEGORY]->(:Code)   (category = the thesis's
                        careplan CODE column; NOT activity codes, for parity)
  Procedure  SNOMED  <- (:Procedure)-[:CODE]->(:Code)      (bridge allow-lists)

Run in the driver venv:
  .../skripsi/.venv/Scripts/python.exe graph_export_ehr_codes.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from neo4j import GraphDatabase

SNOMED = "http://snomed.info/sct"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "fhirneo4j")
DATABASE = os.environ.get("NEO4J_DATABASE", "sihdfhir")

# cobafhirlagi's DBMS import folder (shared by all its databases, incl. sihdfhir).
IMPORT = Path(os.environ.get(
    "NEO4J_IMPORT",
    r"C:\Users\T14s\.Neo4jDesktop2\Data\dbmss"
    r"\dbms-33d1a4ee-3166-40c6-a24c-438282fb1a0e\import",
))

# (output csv, cypher returning DISTINCT code, description)
SOURCES = {
    "conditions.csv": (
        f"MATCH (:Condition)-[:CODE]->(k:Code) WHERE k.system = '{SNOMED}' "
        "RETURN DISTINCT k.code AS code, k.display AS description"
    ),
    "medications.csv": (
        f"MATCH (k:Code) WHERE k.system = '{RXNORM}' "
        "RETURN DISTINCT k.code AS code, k.display AS description"
    ),
    # category = the thesis's careplan CODE (a per-plan concept); activity codes
    # are excluded so the bridged careplan universe matches the thesis's.
    "careplans.csv": (
        f"MATCH (:CarePlan)-[:CATEGORY]->(k:Code) WHERE k.system = '{SNOMED}' "
        "RETURN DISTINCT k.code AS code, k.display AS description"
    ),
    "procedures.csv": (
        f"MATCH (:Procedure)-[:CODE]->(k:Code) WHERE k.system = '{SNOMED}' "
        "RETURN DISTINCT k.code AS code, k.display AS description"
    ),
}


def main() -> None:
    IMPORT.mkdir(parents=True, exist_ok=True)
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print(f"=== graph_export_ehr_codes.py -> {IMPORT} (db={DATABASE}) ===")
    with driver.session(database=DATABASE) as s:
        for fname, cypher in SOURCES.items():
            rows = [(r["code"], r["description"]) for r in s.run(cypher)]
            rows = [(c, d) for c, d in rows if c and d]
            path = IMPORT / fname
            with open(path, "w", newline="", encoding="utf8") as fh:
                w = csv.writer(fh)
                w.writerow(["code", "description"])
                w.writerows(rows)
            print(f"  {fname:18} {len(rows):5} codes")
    driver.close()
    print("Done. Next: snomed_umls_bridge.py --ehr-only (scispacy venv, "
          "NEO4J_IMPORT pointed here).")


if __name__ == "__main__":
    main()
