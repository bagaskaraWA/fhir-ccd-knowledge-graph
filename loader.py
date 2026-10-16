#!/usr/bin/env python3
"""Load Synthea FHIR R4 bundles into Neo4j.

Model:
    (:Resource:<ResourceType> {uid, ...scalars})
      -[:<FIELD>]-> (:Resource)                    resource references
      -[:<FIELD>]-> (:Code {system, code, display}) terminology

Usage:
    python loader.py --dry-run              # validate transform, no database needed
    python loader.py --limit 10 --skip-large
    python loader.py                        # full load
"""

import argparse
import collections
import glob
import json
import os
import re
import sys
import time

DATA_DIR = "synthea_sample_data_fhir_latest"

# Billing/provenance. Nothing clinical references these -- the edges run
# Claim->Encounter, never the reverse -- so dropping them costs no relationships.
# DiagnosticReport is a lab-result container that references the observations
# OBSERVATION_ALLOWLIST drops, so under the allowlist it would mostly orphan;
# the CRS never traverses it, and at 5.5k patients it is ~780k nodes.
SKIP_TYPES = {
    "Claim",
    "ExplanationOfBenefit",
    "DocumentReference",
    "SupplyDelivery",
    "Provenance",
    "DiagnosticReport",
}

# When set, only Observations whose code.coding[] contains one of these LOINC
# codes are loaded -- the CRS-relevant vitals/labs. Empty set = load all.
# Observations are ~44% of the graph; this is the dominant scale lever.
# Systolic 8480-6 / diastolic 8462-4 ride inside the 85354-9 BP panel as
# components, so allowlisting the panel keeps them automatically.
OBSERVATION_ALLOWLIST = {
    "10230-1",  # LVEF
    "39156-5",  # BMI [Ratio]
    "59576-9",  # BMI [Percentile]
    "18262-6",  # LDL cholesterol
    "2093-3",   # total cholesterol
    "2571-8",   # triglycerides
    "4548-4",   # HbA1c
    "72166-2",  # tobacco smoking status
    "85354-9",  # blood pressure panel
}

# Handled as :Code nodes, relationships, or discarded -- never as scalar properties.
# `component` is here because it becomes :Component nodes: flattening a list of
# objects keeps only the first, which drops the systolic half of every blood
# pressure reading.
PROP_SKIP = {
    "text",
    "contained",
    "meta",
    "coding",
    "extension",
    "modifierExtension",
    "component",
}

BATCH = 5000


def is_coding(obj):
    """A Coding vs a Quantity: both carry system+code, but only Quantity has `value`.

    Without this, UCUM units (cm, mg) get promoted to clinical :Code nodes.
    """
    return (
        isinstance(obj, dict)
        and "system" in obj
        and "code" in obj
        and "value" not in obj
    )


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def rel_name(path):
    """Turn a FHIR element path into a relationship type.

    Observation.subject                  -> SUBJECT
    Encounter.location.location          -> LOCATION
    MedicationRequest.reasonReference    -> REASON
    Observation.component.code.coding    -> COMPONENT_CODE
    """
    parts = [p for p in path.split(".")[1:] if p != "coding"]
    cleaned = []
    for p in parts:
        p = re.sub(r"(CodeableConcept|Coding|Reference)$", "", p)
        if p and (not cleaned or cleaned[-1] != p):
            cleaned.append(p)
    out = "_".join(snake(p) for p in cleaned).upper()
    out = re.sub(r"[^A-Z0-9_]", "_", out)
    return out or "REF"


def flatten(obj, prefix, out, depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        if "reference" in obj or is_coding(obj):
            return
        for k, v in obj.items():
            if k in PROP_SKIP:
                continue
            flatten(v, f"{prefix}_{k}" if prefix else k, out, depth + 1)
    elif isinstance(obj, list):
        scalars = [x for x in obj if isinstance(x, (str, int, float, bool))]
        if scalars and len(scalars) == len(obj):
            out.setdefault(prefix, scalars)
        elif obj:
            flatten(obj[0], prefix, out, depth + 1)
    elif obj is not None and prefix:
        out.setdefault(prefix, obj)


def walk(obj, path, refs, codings):
    if isinstance(obj, dict):
        if "reference" in obj and isinstance(obj["reference"], str):
            refs.append((path, obj["reference"]))
            return
        if is_coding(obj):
            codings.append((path, obj))
            return
        for k, v in obj.items():
            if k in ("text", "contained", "component"):
                continue
            walk(v, f"{path}.{k}" if path else k, refs, codings)
    elif isinstance(obj, list):
        for x in obj:
            walk(x, path, refs, codings)


def observation_allowed(resource):
    """True if an Observation carries an allow-listed LOINC (or the list is off)."""
    if not OBSERVATION_ALLOWLIST or resource["resourceType"] != "Observation":
        return True
    codings = resource.get("code", {}).get("coding", [])
    return any(c.get("code") in OBSERVATION_ALLOWLIST for c in codings)


def components(uid, resource):
    """Observation.component pairs a code with a value (systolic + 115 mm[Hg]).

    Both halves must live on one node or the pairing is lost.
    """
    for i, c in enumerate(resource.get("component", [])):
        yield f"{uid}#component-{i}", c


class Loader:
    def __init__(self, driver, dry_run=False, database=None):
        self.driver = driver
        self.dry_run = dry_run
        self.database = database
        self.ident = {}
        self.nodes = collections.defaultdict(list)
        self.rels = collections.defaultdict(list)
        self.codes = []
        self.code_rels = collections.defaultdict(list)
        self.stats = collections.Counter()
        self.unresolved = collections.Counter()

    # -- reference resolution -------------------------------------------------

    def resolve(self, ref, parent_uid):
        """Resolve the three reference forms Synthea emits."""
        if ref.startswith("urn:uuid:"):
            return ref[9:]
        if ref.startswith("#"):
            return f"{parent_uid}#{ref[1:]}"
        m = re.match(r"^([A-Za-z]+)\?identifier=([^|]+)\|(.+)$", ref)
        if m:
            # Conditional reference -- resolves only against the identifier index
            # built from hospitalInformation/practitionerInformation.
            return self.ident.get((m.group(2), m.group(3)))
        m = re.match(r"^([A-Za-z]+)/(.+)$", ref)
        if m:
            return m.group(2)
        return None

    # -- buffering ------------------------------------------------------------

    def add_node(self, uid, rtype, resource):
        props = {}
        flatten(resource, "", props)
        props.pop("id", None)
        props["fhir_id"] = resource.get("id")
        self.nodes[re.sub(r"[^A-Za-z0-9]", "", rtype)].append(
            {"uid": uid, "props": props}
        )
        self.stats[f"node:{rtype}"] += 1

    def add_edges(self, uid, resource, root=None):
        refs, codings = [], []
        walk(resource, root or resource["resourceType"], refs, codings)
        for path, ref in refs:
            dst = self.resolve(ref, uid)
            if dst is None:
                self.unresolved[ref.split("?")[0][:40]] += 1
                continue
            self.rels[rel_name(path)].append({"src": uid, "dst": dst})
            self.stats["rel"] += 1
        for path, c in codings:
            self.codes.append(
                {
                    "system": c["system"],
                    "code": str(c["code"]),
                    "display": c.get("display"),
                }
            )
            self.code_rels[rel_name(path)].append(
                {"src": uid, "system": c["system"], "code": str(c["code"])}
            )
            self.stats["code_rel"] += 1

    def pending(self):
        return (
            sum(len(v) for v in self.nodes.values())
            + sum(len(v) for v in self.rels.values())
            + len(self.codes)
            + sum(len(v) for v in self.code_rels.values())
        )

    # -- writing --------------------------------------------------------------

    def _session(self):
        if self.database:
            return self.driver.session(database=self.database)
        return self.driver.session()

    def create_database(self):
        """Provision the target database (Enterprise) so it need not pre-exist."""
        if self.dry_run or not self.database or self.database == "neo4j":
            return
        with self.driver.session(database="system") as s:
            s.run(f"CREATE DATABASE `{self.database}` IF NOT EXISTS WAIT").consume()

    def schema(self):
        if self.dry_run:
            return
        stmts = [
            "CREATE CONSTRAINT resource_uid IF NOT EXISTS "
            "FOR (r:Resource) REQUIRE r.uid IS UNIQUE",
            "CREATE CONSTRAINT code_key IF NOT EXISTS "
            "FOR (c:Code) REQUIRE (c.system, c.code) IS NODE KEY",
        ]
        with self._session() as s:
            for q in stmts:
                try:
                    s.run(q)
                except Exception as e:
                    # NODE KEY is Enterprise-only; fall back to a plain index.
                    print(f"  ! {e.__class__.__name__}: falling back", file=sys.stderr)
                    s.run(
                        "CREATE INDEX code_key IF NOT EXISTS "
                        "FOR (c:Code) ON (c.system, c.code)"
                    )

    def flush(self):
        if self.dry_run:
            self.nodes.clear()
            self.rels.clear()
            self.codes.clear()
            self.code_rels.clear()
            return

        with self._session() as s:
            for rtype, rows in self.nodes.items():
                s.execute_write(
                    lambda tx, rt=rtype, rs=rows: tx.run(
                        f"UNWIND $rows AS row "
                        f"MERGE (n:Resource {{uid: row.uid}}) "
                        f"SET n += row.props SET n:`{rt}`",
                        rows=rs,
                    ).consume()
                )
            if self.codes:
                s.execute_write(
                    lambda tx, rs=self.codes: tx.run(
                        "UNWIND $rows AS row "
                        "MERGE (c:Code {system: row.system, code: row.code}) "
                        "ON CREATE SET c.display = row.display",
                        rows=rs,
                    ).consume()
                )
            for rt, rows in self.rels.items():
                res = s.execute_write(
                    lambda tx, r=rt, rs=rows: tx.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (s:Resource {{uid: row.src}}) "
                        f"MATCH (t:Resource {{uid: row.dst}}) "
                        f"MERGE (s)-[:`{r}`]->(t) "
                        f"RETURN count(*) AS n",
                        rows=rs,
                    ).single()["n"]
                )
                # A silent shortfall means a MATCH found no node -- surface it.
                if res < len(rows):
                    self.stats["rel_unmatched"] += len(rows) - res
            for rt, rows in self.code_rels.items():
                s.execute_write(
                    lambda tx, r=rt, rs=rows: tx.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (s:Resource {{uid: row.src}}) "
                        f"MATCH (c:Code {{system: row.system, code: row.code}}) "
                        f"MERGE (s)-[:`{r}`]->(c)",
                        rows=rs,
                    ).consume()
                )

        self.nodes.clear()
        self.rels.clear()
        self.codes.clear()
        self.code_rels.clear()

    # -- bundles --------------------------------------------------------------

    def index_identifiers(self, path):
        """Build (system, value) -> uid so conditional references can resolve."""
        d = json.load(open(path, encoding="utf8"))
        for e in d["entry"]:
            r = e["resource"]
            uid = e["fullUrl"].replace("urn:uuid:", "")
            for i in r.get("identifier", []):
                if "system" in i and "value" in i:
                    self.ident[(i["system"], str(i["value"]))] = uid

    def load_bundle(self, path):
        d = json.load(open(path, encoding="utf8"))
        entries = [
            e
            for e in d.get("entry", [])
            if e["resource"]["resourceType"] not in SKIP_TYPES
            and observation_allowed(e["resource"])
        ]

        for e in entries:
            uid = e.get("fullUrl", "").replace("urn:uuid:", "")
            r = e["resource"]
            if not uid:
                continue
            self.add_node(uid, r["resourceType"], r)
            for cuid, c in components(uid, r):
                self.add_node(cuid, "Component", c)
            for c in r.get("contained", []):
                self.add_node(f"{uid}#{c['id']}", c["resourceType"], c)

        # Nodes for the whole bundle land before its edges, so no MATCH
        # depends on entry ordering within the file.
        self.flush()

        for e in entries:
            uid = e.get("fullUrl", "").replace("urn:uuid:", "")
            r = e["resource"]
            if not uid:
                continue
            self.add_edges(uid, r)
            for cuid, c in components(uid, r):
                self.rels["COMPONENT"].append({"src": uid, "dst": cuid})
                self.stats["rel"] += 1
                self.add_edges(cuid, c, root="Component")
            for c in r.get("contained", []):
                self.add_edges(f"{uid}#{c['id']}", c)
            if self.pending() > BATCH:
                self.flush()
        self.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no database required")
    ap.add_argument("--limit", type=int, help="only N patient bundles")
    ap.add_argument("--skip-large", action="store_true", help="skip bundles >20MB")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "fhirneo4j"))
    ap.add_argument("--data", default=DATA_DIR)
    ap.add_argument(
        "--database",
        default=os.environ.get("NEO4J_DATABASE", "neo4j"),
        help="target database; created if absent (Enterprise)",
    )
    args = ap.parse_args()

    driver = None
    if not args.dry_run:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        driver.verify_connectivity()

    ld = Loader(driver, dry_run=args.dry_run, database=args.database)
    ld.create_database()
    ld.schema()

    files = sorted(glob.glob(os.path.join(args.data, "*.json")))
    info = [f for f in files if os.path.basename(f).startswith(("hospital", "practitioner"))]
    patients = [f for f in files if f not in info]

    if args.skip_large:
        patients = [f for f in patients if os.path.getsize(f) < 20_000_000]
    if args.limit:
        patients = sorted(patients, key=os.path.getsize)[: args.limit]

    t0 = time.time()

    # Conditional references point here, so this must complete before any bundle.
    for f in info:
        ld.index_identifiers(f)
    print(f"identifier index: {len(ld.ident)} entries")
    for f in info:
        ld.load_bundle(f)
    print(f"loaded {len(info)} reference bundles")

    for i, f in enumerate(patients, 1):
        ld.load_bundle(f)
        if i % 10 == 0 or i == len(patients):
            print(
                f"  [{i}/{len(patients)}] {ld.stats['rel']:,} rels  "
                f"{time.time()-t0:.0f}s",
                flush=True,
            )

    target = "(dry run)" if args.dry_run else f"database '{args.database}'"
    print(f"\n{'DRY RUN' if args.dry_run else 'LOAD'} complete in {time.time()-t0:.0f}s -> {target}")
    nodes = {k[5:]: v for k, v in ld.stats.items() if k.startswith("node:")}
    print(f"  resource nodes : {sum(nodes.values()):,}")
    print(f"  reference rels : {ld.stats['rel']:,}")
    print(f"  code rels      : {ld.stats['code_rel']:,}")
    if ld.stats["rel_unmatched"]:
        print(f"  ! unmatched rels: {ld.stats['rel_unmatched']:,}")
    print("\n  by type:")
    for k, v in sorted(nodes.items(), key=lambda x: -x[1]):
        print(f"    {k:28} {v:7,}")
    if ld.unresolved:
        print(f"\n  unresolved references ({sum(ld.unresolved.values()):,}):")
        for k, v in ld.unresolved.most_common(10):
            print(f"    {v:7,}  {k}")

    if driver:
        driver.close()


if __name__ == "__main__":
    main()
