PATIENT 3875c68d-c8e7-bef8-d96f-cb513c6cf29f
Label each rec in worksheet_3875c68d-c8e7-bef8-d96f-cb513c6cf29f.csv against THIS record + the guideline text.

OBSERVATIONS (needed for the observation-gated recs):
  LVEF (worst/min)   : None
  BMI  (max)         : 24.57
  LDL  (max)         : 143.05
  TG   (max)         : 200.85   (LIPID:9: LDL<100 & TG 150-499)
  BP   (most-recent) : 107/87
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
    - Referral to transplant surgeon (procedure)
    - Transplant of kidney (procedure)
    - Transplantation of kidney regime (regime/therapy)

CONDITIONS (36):
  - Abnormal findings diagnostic imaging heart+coronary circulat (finding)
  - Acute non-ST segment elevation myocardial infarction (disorder)
  - Acute viral pharyngitis (disorder)
  - Anemia (disorder)
  - Awaiting transplantation of kidney (situation)
  - Chronic kidney disease stage 1 (disorder)
  - Chronic kidney disease stage 3 (disorder)
  - Chronic kidney disease stage 4 (disorder)
  - Disorder of kidney due to diabetes mellitus (disorder)
  - End-stage renal disease (disorder)
  - Essential hypertension (disorder)
  - Full-time employment (finding)
  - Gingivitis (disorder)
  - History of coronary artery bypass grafting (situation)
  - History of myocardial infarction (situation)
  - History of renal transplant (situation)
  - Housing unsatisfactory (finding)
  - Ischemic heart disease (disorder)
  - Limited social contact (finding)
  - Medication review due (situation)
  - Microalbuminuria due to type 2 diabetes mellitus (disorder)
  - Myocardial infarction (disorder)
  - Not in labor force (finding)
  - Part-time employment (finding)
  - Prediabetes (finding)
  - Primary dental caries (disorder)
  - Proteinuria due to type 2 diabetes mellitus (disorder)
  - Received higher education (finding)
  - Reports of violence in the environment (finding)
  - Risk activity involvement (finding)
  - Severe anxiety (panic) (finding)
  - Stress (finding)
  - Unemployed (finding)
  - Unhealthy alcohol drinking behavior (finding)
  - Victim of intimate partner abuse (finding)
  - Viral sinusitis (disorder)

MEDICATIONS (20):
  - 1 ML Epoetin Alfa 4000 UNT/ML Injection [Epogen]
  - 1 ML tacrolimus 5 MG/ML Injection [Prograf]
  - 24 HR metoprolol succinate 100 MG Extended Release Oral Tablet
  - 24 HR tacrolimus 1 MG Extended Release Oral Tablet [Envarsus]
  - Amoxicillin 250 MG / Clavulanate 125 MG Oral Tablet
  - Clopidogrel 75 MG Oral Tablet
  - Hydrochlorothiazide 25 MG Oral Tablet
  - Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray
  - Simvastatin 20 MG Oral Tablet
  - aspirin 325 MG Oral Tablet
  - aspirin 81 MG Oral Tablet
  - atorvastatin 10 MG Oral Tablet
  - clopidogrel 300 MG Oral Tablet
  - heparin sodium, porcine 100 UNT/ML Injectable Solution
  - insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
  - losartan potassium 100 MG Oral Tablet
  - metoprolol tartrate 50 MG Oral Tablet
  - nitroglycerin 0.4 MG Sublingual Tablet
  - prasugrel 10 MG Oral Tablet
  - sodium fluoride 0.0272 MG/MG Oral Gel
