PATIENT 1db4196c-6fab-b290-a4a7-fe3573725cef
Label each rec in worksheet_1db4196c-6fab-b290-a4a7-fe3573725cef.csv against THIS record + the guideline text.

OBSERVATIONS (needed for the observation-gated recs):
  LVEF (worst/min)   : None
  BMI  (max)         : 28.11
  LDL  (max)         : 172.75
  TG   (max)         : 213.26   (LIPID:9: LDL<100 & TG 150-499)
  BP   (most-recent) : 122/80
  smoker (recent)    : False

ANTICOAGULATION (drives APT:1, APT:11-16):
  warfarin            : no
  any OAC             : no   (warfarin/apixaban/rivaroxaban/dabigatran/edoxaban)
  atrial fibrillation : no
  -> requires OAC     : no   (on an OAC OR has AF)

NSAID USE (APT:10 chronic NSAID -- from CSV course durations, not the graph):
  courses (episodes)  : 0
  cumulative days     : 0
  longest course (d)  : 0
  -> chronic NSAID    : no   (>90d cumulative OR >=3 courses OR any single >30d)

PROCEDURES / INTERVENTIONS (PCI is procedure-only -> drives APT:2, APT:11, CR:1:1):
  PCI (415070008)     : yes
    - Percutaneous coronary intervention
    - Pretransplant evaluation of kidney recipient (procedure)
    - Transplant of kidney (procedure)
    - Transplantation of kidney regime (regime/therapy)

CONDITIONS (41):
  - Abnormal findings diagnostic imaging heart+coronary circulat (finding)
  - Acute non-ST segment elevation myocardial infarction (disorder)
  - Anemia (disorder)
  - Awaiting transplantation of kidney (situation)
  - Body mass index 30+ - obesity (finding)
  - Carcinoma in situ of prostate (disorder)
  - Chronic intractable migraine without aura (disorder)
  - Chronic kidney disease stage 1 (disorder)
  - Chronic kidney disease stage 2 (disorder)
  - Chronic kidney disease stage 3 (disorder)
  - Chronic kidney disease stage 4 (disorder)
  - Disorder of kidney due to diabetes mellitus (disorder)
  - Essential hypertension (disorder)
  - Fractured dental filling (finding)
  - Full-time employment (finding)
  - Gingivitis (disorder)
  - Has a criminal record (finding)
  - History of appendectomy (situation)
  - History of coronary artery bypass grafting (situation)
  - History of myocardial infarction (situation)
  - History of renal transplant (situation)
  - Hyperlipidemia (disorder)
  - Ischemic heart disease (disorder)
  - Limited social contact (finding)
  - Loss of teeth (disorder)
  - Medication review due (situation)
  - Metabolic syndrome X (disorder)
  - Microalbuminuria due to type 2 diabetes mellitus (disorder)
  - Myocardial infarction (disorder)
  - Neoplasm of prostate (disorder)
  - Not in labor force (finding)
  - Part-time employment (finding)
  - Prediabetes (finding)
  - Primary dental caries (disorder)
  - Proteinuria due to type 2 diabetes mellitus (disorder)
  - Received higher education (finding)
  - Reports of violence in the environment (finding)
  - Serving in military service (finding)
  - Social isolation (finding)
  - Stress (finding)
  - Suspected prostate cancer (situation)

MEDICATIONS (21):
  - 0.25 ML Leuprolide Acetate 30 MG/ML Prefilled Syringe
  - 1 ML DOCEtaxel 20 MG/ML Injection
  - 1 ML Epoetin Alfa 4000 UNT/ML Injection [Epogen]
  - 1 ML tacrolimus 5 MG/ML Injection [Prograf]
  - 24 HR metoprolol succinate 100 MG Extended Release Oral Tablet
  - 24 HR metoprolol succinate 25 MG Extended Release Oral Tablet
  - 24 HR tacrolimus 1 MG Extended Release Oral Tablet [Envarsus]
  - 50 ML bivalirudin 5 MG/ML Injection
  - Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray
  - Simvastatin 10 MG Oral Tablet
  - Simvastatin 20 MG Oral Tablet
  - aspirin 325 MG Oral Tablet
  - aspirin 81 MG Oral Tablet
  - atorvastatin 40 MG Oral Tablet
  - benazepril hydrochloride 40 MG Oral Tablet
  - clopidogrel 300 MG Oral Tablet
  - insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
  - lisinopril 10 MG Oral Tablet
  - nitroglycerin 0.4 MG Sublingual Tablet
  - prasugrel 10 MG Oral Tablet
  - sodium fluoride 0.0272 MG/MG Oral Gel
