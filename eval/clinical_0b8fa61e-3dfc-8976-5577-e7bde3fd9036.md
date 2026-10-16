PATIENT 0b8fa61e-3dfc-8976-5577-e7bde3fd9036
Label each rec in worksheet_0b8fa61e-3dfc-8976-5577-e7bde3fd9036.csv against THIS record + the guideline text.

OBSERVATIONS (needed for the observation-gated recs):
  LVEF (worst/min)   : None
  BMI  (max)         : 27.69
  LDL  (max)         : 148.45
  TG   (max)         : 189.36   (LIPID:9: LDL<100 & TG 150-499)
  BP   (most-recent) : 141/84
  smoker (recent)    : False

ANTICOAGULATION (drives APT:1, APT:11-16):
  warfarin            : no
  any OAC             : no   (warfarin/apixaban/rivaroxaban/dabigatran/edoxaban)
  atrial fibrillation : no
  -> requires OAC     : no   (on an OAC OR has AF)

NSAID USE (APT:10 chronic NSAID -- from CSV course durations, not the graph):
  courses (episodes)  : 1
  cumulative days     : 59
  longest course (d)  : 59
  -> chronic NSAID    : yes   (>90d cumulative OR >=3 courses OR any single >30d)

PROCEDURES / INTERVENTIONS (PCI is procedure-only -> drives APT:2, APT:11, CR:1:1):
  PCI (415070008)     : no
    (no key cardiac-intervention procedures)

CONDITIONS (50):
  - Abnormal findings diagnostic imaging heart+coronary circulat (finding)
  - Acute ST segment elevation myocardial infarction (disorder)
  - Acute infective cystitis (disorder)
  - Acute viral pharyngitis (disorder)
  - Alcoholism (disorder)
  - Anemia (disorder)
  - Carcinoma in situ of prostate (disorder)
  - Chronic kidney disease stage 1 (disorder)
  - Chronic kidney disease stage 2 (disorder)
  - Chronic low back pain (finding)
  - Chronic pain (finding)
  - Disease caused by severe acute respiratory syndrome coronavirus 2 (disorder)
  - Disorder of kidney due to diabetes mellitus (disorder)
  - Educated to high school level (finding)
  - Essential hypertension (disorder)
  - Fever (finding)
  - Fracture of bone (disorder)
  - Fracture of clavicle (disorder)
  - Full-time employment (finding)
  - Gingival disease (disorder)
  - Gingivitis (disorder)
  - History of coronary artery bypass grafting (situation)
  - History of myocardial infarction (situation)
  - History of peripheral stem cell transplant (situation)
  - History of renal transplant (situation)
  - Hyperlipidemia (disorder)
  - Ischemic heart disease (disorder)
  - Lack of access to transportation (finding)
  - Loss of teeth (disorder)
  - Medication review due (situation)
  - Microalbuminuria due to type 2 diabetes mellitus (disorder)
  - Neoplasm of prostate (disorder)
  - Non-small cell carcinoma of lung, TNM stage 1 (disorder)
  - Non-small cell lung cancer (disorder)
  - Not in labor force (finding)
  - Obstructive sleep apnea syndrome (disorder)
  - Part-time employment (finding)
  - Prediabetes (finding)
  - Proteinuria due to type 2 diabetes mellitus (disorder)
  - Recurrent urinary tract infection (disorder)
  - Reports of violence in the environment (finding)
  - Serving in military service (finding)
  - Sleep disorder (disorder)
  - Social isolation (finding)
  - Stress (finding)
  - Suspected disease caused by Severe acute respiratory coronavirus 2 (situation)
  - Suspected lung cancer (situation)
  - Transport problem (finding)
  - Unemployed (finding)
  - Victim of intimate partner abuse (finding)

MEDICATIONS (20):
  - 24 HR metoprolol succinate 100 MG Extended Release Oral Tablet
  - 24 HR tacrolimus 1 MG Extended Release Oral Tablet [Envarsus]
  - Acetaminophen 325 MG / HYDROcodone Bitartrate 7.5 MG Oral Tablet
  - Cisplatin 50 MG Injection
  - Hydrochlorothiazide 25 MG Oral Tablet
  - Naproxen sodium 220 MG Oral Tablet
  - Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray
  - PACLitaxel 100 MG Injection
  - Simvastatin 10 MG Oral Tablet
  - Simvastatin 20 MG Oral Tablet
  - Vitamin B12 5 MG/ML Injectable Solution
  - aspirin 81 MG Oral Tablet
  - benazepril hydrochloride 40 MG Oral Tablet
  - cephalexin 500 MG Oral Tablet
  - ciprofloxacin 500 MG Oral Tablet
  - insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
  - metoprolol tartrate 100 MG Oral Tablet
  - prasugrel 10 MG Oral Tablet
  - sodium fluoride 0.0272 MG/MG Oral Gel
  - sulfamethoxazole 800 MG / trimethoprim 160 MG Oral Tablet
