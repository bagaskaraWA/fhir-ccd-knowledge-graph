PATIENT 2b050f16-69a5-be03-034a-fbc080ec9ed6
Label each rec in worksheet_2b050f16-69a5-be03-034a-fbc080ec9ed6.csv against THIS record + the guideline text.

OBSERVATIONS (needed for the observation-gated recs):
  LVEF (worst/min)   : None
  BMI  (max)         : 30.34
  LDL  (max)         : 245.85
  TG   (max)         : 149.73   (LIPID:9: LDL<100 & TG 150-499)
  BP   (most-recent) : 98/70
  smoker (recent)    : False

ANTICOAGULATION (drives APT:1, APT:11-16):
  warfarin            : no
  any OAC             : no   (warfarin/apixaban/rivaroxaban/dabigatran/edoxaban)
  atrial fibrillation : no
  -> requires OAC     : no   (on an OAC OR has AF)

NSAID USE (APT:10 chronic NSAID -- from CSV course durations, not the graph):
  courses (episodes)  : 2
  cumulative days     : 160
  longest course (d)  : 140
  -> chronic NSAID    : yes   (>90d cumulative OR >=3 courses OR any single >30d)

PROCEDURES / INTERVENTIONS (PCI is procedure-only -> drives APT:2, APT:11, CR:1:1):
  PCI (415070008)     : no
    - Pretransplant evaluation of kidney recipient (procedure)
    - Referral to transplant surgeon (procedure)
    - Transplant of kidney (procedure)
    - Transplantation of kidney regime (regime/therapy)

CONDITIONS (49):
  - Abnormal findings diagnostic imaging heart+coronary circulat (finding)
  - Acute bronchitis (disorder)
  - Anemia (disorder)
  - Awaiting transplantation of kidney (situation)
  - Body mass index 30+ - obesity (finding)
  - Chronic kidney disease stage 1 (disorder)
  - Chronic kidney disease stage 2 (disorder)
  - Chronic kidney disease stage 3 (disorder)
  - Chronic kidney disease stage 4 (disorder)
  - Dental filling lost (finding)
  - Diabetes mellitus type 2 (disorder)
  - Disorder of kidney due to diabetes mellitus (disorder)
  - Essential hypertension (disorder)
  - Fractured dental filling (finding)
  - Full-time employment (finding)
  - Gingival disease (disorder)
  - Gingivitis (disorder)
  - History of coronary artery bypass grafting (situation)
  - History of renal transplant (situation)
  - Hyperglycemia (disorder)
  - Hypertriglyceridemia (disorder)
  - Injury of knee (disorder)
  - Ischemic heart disease (disorder)
  - Leaking dental filling (finding)
  - Limited social contact (finding)
  - Loss of teeth (disorder)
  - Medication review due (situation)
  - Metabolic syndrome X (disorder)
  - Microalbuminuria due to type 2 diabetes mellitus (disorder)
  - Neuropathy due to type 2 diabetes mellitus (disorder)
  - Nonproliferative diabetic retinopathy due to type II diabetes mellitus
  - Not in labor force (finding)
  - Part-time employment (finding)
  - Prediabetes (finding)
  - Primary dental caries (disorder)
  - Proteinuria due to type 2 diabetes mellitus (disorder)
  - Received higher education (finding)
  - Reports of violence in the environment (finding)
  - Risk activity involvement (finding)
  - Rupture of patellar tendon (disorder)
  - Severe anxiety (panic) (finding)
  - Social isolation (finding)
  - Sprain (morphologic abnormality)
  - Sprain of ankle (disorder)
  - Stress (finding)
  - Unemployed (finding)
  - Unhealthy alcohol drinking behavior (finding)
  - Victim of intimate partner abuse (finding)
  - Viral sinusitis (disorder)

MEDICATIONS (13):
  - 1 ML Epoetin Alfa 4000 UNT/ML Injection [Epogen]
  - 1 ML tacrolimus 5 MG/ML Injection [Prograf]
  - 24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet
  - 24 HR metoprolol succinate 100 MG Extended Release Oral Tablet
  - 24 HR tacrolimus 1 MG Extended Release Oral Tablet [Envarsus]
  - Acetaminophen 21.7 MG/ML / Dextromethorphan Hydrobromide 1 MG/ML / doxylamine succinate 0.417 MG/ML Oral Solution
  - Ibuprofen 200 MG Oral Tablet
  - Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray
  - amLODIPine 2.5 MG Oral Tablet
  - insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
  - lisinopril 10 MG Oral Tablet
  - sodium fluoride 0.0272 MG/MG Oral Gel
  - tropicamide 5 MG/ML Ophthalmic Solution
