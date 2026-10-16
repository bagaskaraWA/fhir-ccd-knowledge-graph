# FHIR-native knowledge graph for clinical recommendation in chronic coronary disease

Source code, evaluation outputs and LaTeX sources of the bachelor's thesis

> Bagaskara Waskita Ahmad (2026). *Pengembangan Sistem Rekomendasi Klinis untuk Penyakit
> Jantung Koroner Kronis Menggunakan Knowledge Graph Berbasis Rekam Medis FHIR, Panduan
> Klinis, dan Literatur Biomedis* [Development of a Clinical Recommendation System for Chronic
> Coronary Disease Using a Knowledge Graph Built From FHIR Electronic Health Records, Clinical
> Guidelines, and Biomedical Literature]. Skripsi, Program Studi Teknik Biomedis, Departemen
> Teknik Elektro dan Teknologi Informasi, Fakultas Teknik, Universitas Gadjah Mada.

All patient data in this work are **synthetic** (generated with Synthea). No real patient
information is used or included.

## What the system does

- **Knowledge graph.** HL7 FHIR R4 bundles for 5,490 synthetic patients are loaded into a
  Neo4j property graph and fused with the 2023 AHA/ACC chronic coronary disease (CCD)
  guideline and 4,801 PubMed abstracts through a UMLS concept layer: 1,804,379 nodes and
  8,796,425 relationships over 25 labels, 51 relationship types and 26 code systems.
- **Observation gates.** Recommendations conditioned on a measured value (ejection fraction,
  body-mass index, blood pressure, lipids) are gated on the patient's actual measurements.
  Over 876 CCD patients, gating raises guideline-concordance F1 from 0.743 to 0.810; the
  whole gain sits in the 15 of 68 recommendations that are gated.
- **Grounded briefing.** Facts are retrieved deterministically with Cypher, each carrying a
  recommendation ID, class of recommendation and PMIDs; a large language model only phrases
  them, and an automated check makes citation-level faithfulness decidable.
- **Evaluation.**
  - A reference standard computed from the raw FHIR bundles, validated against 30 manually
    labelled patients (Cohen's κ = 0.991, 95% CI 0.984–0.996).
  - A rebuild of the gate from Synthea's CSV export: none of 13,140 decisions change.
  - A clinician review of 327 recommendations for 20 patients.

The thesis (`template_thesis_latex_dteti-id-noreview/`) states the limits of each result.

## Repository layout

| Path | Contents |
|---|---|
| `loader.py` | FHIR R4 bundles → Neo4j (idempotent `MERGE`) |
| `graph_export_ehr_codes.py`, `snomed_umls_bridge.py` | export the graph's codes and map them to UMLS CUIs |
| `ehr_concept_kg.cypher`, `literature_kg.cypher`, `guideline_kg.cypher` | concept, literature and guideline layers |
| `cohort.cypher`, `queries.cypher`, `thesis_port_patterns.cypher` | cohort gate and query patterns |
| `crs_eval.py`, `obs_gate.py`, `eval_by_class.py` | applicable-recommendation set, observation gates, concordance per class |
| `silver_oracle.py`, `predicate_audit.py`, `csv_gate.py`, `nsaid_csv.py` | reference standard from the raw bundles; its audits and the CSV rebuild |
| `make_worksheets.py`, `build_gold_labels.py`, `pick_review_patients.py`, `kappa_bootstrap.py` | gold-standard sample, worksheets, κ with bootstrap intervals |
| `crs_briefing.py`, `crs_briefing_openai.py`, `faithfulness_check.py` | grounded briefing and its automated check |
| `subjektif_audit.py`, `make_chart.py`, `make_clean.py`, `graphrag_demo.py` | data audit, figures, utilities |
| `guideline_recommendations.csv`, `guideline_citations.csv`, `guideline_concepts.csv`, `concepts.csv`, `abstracts.csv`, `abstract_concept_edges.csv` | inputs to the graph layers (see *Data availability*) |
| `eval/` | labels, worksheets, generated briefings and facts, and the text reports behind the main evaluation figures |
| `telaah-klinisi/` | clinician-review toolchain; `hasil/penilaian.csv` holds the ratings under codes A/B/C |
| `template_thesis_latex_dteti-id-noreview/` | the thesis in Indonesian (the submitted version) |
| `template_thesis_latex_dteti-master-noreview/` | the same thesis in English |
| `template-makalah-latex-dteti-master/` | an IEEE-format paper on the work |
| `deck-figures/` | figures |

## Build order

| # | Step | Produces |
|---|---|---|
| 1 | `loader.py` | FHIR R4 bundles → Neo4j database `sihdfhir` |
| 2 | `graph_export_ehr_codes.py` | the graph's EHR codes as CSV |
| 3 | `snomed_umls_bridge.py --ehr-only` | codes → UMLS CUIs (three-pass scispaCy linker) |
| 4 | `ehr_concept_kg.cypher` | `:Concept` nodes and `SAME_CONCEPT` edges |
| 5 | `literature_kg.cypher` | PubMed abstracts, mentions, PMI co-occurrence |
| 6 | `guideline_kg.cypher` | recommendations, COR-derived edges, citations |
| 7 | `crs_eval.py`, `obs_gate.py` | applicable set and observation gates |
| 8 | `silver_oracle.py label` | reference standard, read from the **raw bundles** only |
| 9 | `eval_by_class.py` | concordance per discrimination class |

Steps 4 and 6 depend on the output of steps 3 and 5. The reference standard must never
read Neo4j or the system's output; that independence is what makes the evaluation
meaningful.

## Environment

- **Neo4j** 2026.05 Enterprise (Neo4j Desktop 2.2.1). Connection settings come from
  `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD`.
- **Python 3.14** for the loader, the recommendation system and the evaluation:
  `neo4j` 6.2, `anthropic` 0.112, `biopython` 1.87.
- **Python 3.11** for the NLP stack, which `nmslib` pins below 3.12:
  - `scispacy` 0.6.2 with the `en_core_sci_md` 0.5.4 model;
  - `spacy` 3.7.5, `numpy` 1.26.4, `scikit-learn` 1.8.0, `pandas` 3.0.3.
- **Language-model API key:** the briefing scripts read it from the environment. Keys are
  never stored in this repository.

## Data availability

Some inputs cannot be redistributed, so this repository omits them. Everything else needed
to inspect the results is included.

- **Synthetic patients (not included, ~18 GB).** Regenerate them with Synthea build
  `aa0772f`, Massachusetts, 10 years of history, in two runs:
  - module `stable_ischemic_heart_disease`, 2,009 patients, seed `1784186620874`;
  - all modules, 3,481 patients, seed `1784186859476`.
- **Guideline text (removed).** The recommendation statements of the 2023 AHA/ACC chronic
  coronary disease guideline (Virani *et al.*) are copyrighted. They have been removed from:
  - the `text` column of `guideline_recommendations.csv`, `eval/worksheet_*.csv` and
    `eval/safety_worksheet.csv`;
  - the `text` fields of `eval/briefing_facts_*.json`.

  Recommendation IDs (`CCD-2023:<section>:<number>`), class of recommendation, level of
  evidence, intervention type, target and condition CUIs, and cited PMIDs are kept.
  Restore the text from the published guideline before running `guideline_kg.cypher`.
- **UMLS concept names (removed).** `concepts.csv` and `guideline_concepts.csv` keep CUIs
  and semantic types but not names. Rebuilding names and the terminology bridge requires a
  UMLS licence (UTS account) and the scispaCy UMLS linker.
- **PubMed abstracts.** Only PMIDs are stored. Abstracts can be fetched with NCBI
  E-utilities, for example through Biopython.
- **Clinician review.** Ratings are published under rater codes A/B/C only, as promised to
  the raters. The completed rating sheets are not included.

## Licence

- **Code:** MIT; see [`LICENSE`](LICENSE).
- **Thesis, paper and documentation text:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Third-party material keeps its own licence:**
  - the DTETI UGM thesis template (MIT, © 2018 Canggih Puspo Wibowo; see `LICENSE` in each
    thesis folder);
  - `IEEEtran` (LPPL);
  - the bundled LaTeX packages.
- **Not included:** the AHA/ACC guideline content and UMLS content.

## Citation

```bibtex
@thesis{ahmad2026ccdkg,
  author = {Ahmad, Bagaskara Waskita},
  title  = {Pengembangan Sistem Rekomendasi Klinis untuk Penyakit Jantung Koroner Kronis
            Menggunakan Knowledge Graph Berbasis Rekam Medis FHIR, Panduan Klinis, dan
            Literatur Biomedis},
  type   = {Skripsi},
  school = {Universitas Gadjah Mada},
  year   = {2026}
}
```
