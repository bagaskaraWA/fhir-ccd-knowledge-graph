PATIENT 227e76d8-eef1-d5c9-cd5f-3e74b1dca54e
Label each rec in worksheet_227e76d8-eef1-d5c9-cd5f-3e74b1dca54e.csv against THIS record + the guideline text.

OBSERVATIONS (needed for the observation-gated recs):
  LVEF (worst/min)   : None
  BMI  (max)         : 27.66
  LDL  (max)         : 150.97
  TG   (max)         : 370.34   (LIPID:9: LDL<100 & TG 150-499)
  BP   (most-recent) : 121/61
  smoker (recent)    : False

ANTICOAGULATION (drives APT:1, APT:11-16):
  warfarin            : no
  any OAC             : no   (warfarin/apixaban/rivaroxaban/dabigatran/edoxaban)
  atrial fibrillation : no
  -> requires OAC     : no   (on an OAC OR has AF)

NSAID USE (APT:10 chronic NSAID -- from CSV course durations, not the graph):
  courses (episodes)  : 55
  cumulative days     : 3857
  longest course (d)  : 371
  -> chronic NSAID    : yes   (>90d cumulative OR >=3 courses OR any single >30d)

PROCEDURES / INTERVENTIONS (PCI is procedure-only -> drives APT:2, APT:11, CR:1:1):
  PCI (415070008)     : yes
    - Percutaneous coronary intervention

CONDITIONS (46):
  - Abnormal findings diagnostic imaging heart+coronary circulat (finding)
  - Acute viral pharyngitis (disorder)
  - Alzheimer's disease (disorder)
  - Anemia (disorder)
  - Body mass index 30+ - obesity (finding)
  - Chronic kidney disease stage 1 (disorder)
  - Chronic kidney disease stage 2 (disorder)
  - Chronic low back pain (finding)
  - Chronic neck pain (finding)
  - Chronic pain (finding)
  - Chronic sinusitis (disorder)
  - Disorder of kidney due to diabetes mellitus (disorder)
  - Educated to high school level (finding)
  - Essential hypertension (disorder)
  - Fracture of bone (disorder)
  - Fracture of forearm (disorder)
  - Full-time employment (finding)
  - Gingival disease (disorder)
  - Gingivitis (disorder)
  - Has a criminal record (finding)
  - History of coronary artery bypass grafting (situation)
  - History of myocardial infarction (situation)
  - History of seizure (situation)
  - Hyperlipidemia (disorder)
  - Infection of tooth (disorder)
  - Ischemic heart disease (disorder)
  - Limited social contact (finding)
  - Loose dental filling (finding)
  - Loss of teeth (disorder)
  - Medication review due (situation)
  - Metabolic syndrome X (disorder)
  - Microalbuminuria due to type 2 diabetes mellitus (disorder)
  - Myocardial infarction (disorder)
  - Not in labor force (finding)
  - Osteoporosis (disorder)
  - Osteoporotic fracture of bone (disorder)
  - Part-time employment (finding)
  - Prediabetes (finding)
  - Preinfarction syndrome (disorder)
  - Primary dental caries (disorder)
  - Reports of violence in the environment (finding)
  - Seizure disorder (disorder)
  - Sinusitis (disorder)
  - Social isolation (finding)
  - Stress (finding)
  - Victim of intimate partner abuse (finding)

MEDICATIONS (22):
  - 24 HR Donepezil hydrochloride 10 MG / Memantine hydrochloride 28 MG Extended Release Oral Capsule
  - 24 HR metoprolol succinate 100 MG Extended Release Oral Tablet
  - 24 HR metoprolol succinate 50 MG Extended Release Oral Tablet
  - Acetaminophen 325 MG Oral Tablet
  - Alendronic acid 10 MG Oral Tablet
  - Clopidogrel 75 MG Oral Tablet
  - Galantamine 4 MG Oral Tablet
  - Hydrochlorothiazide 25 MG Oral Tablet
  - Ibuprofen 400 MG Oral Tablet [Ibu]
  - Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray
  - Simvastatin 10 MG Oral Tablet
  - Simvastatin 20 MG Oral Tablet
  - aspirin 325 MG Oral Tablet
  - aspirin 81 MG Oral Tablet
  - heparin sodium, porcine 100 UNT/ML Injectable Solution
  - insulin isophane, human 70 UNT/ML / insulin, regular, human 30 UNT/ML Injectable Suspension [Humulin]
  - lisinopril 10 MG Oral Tablet
  - losartan potassium 25 MG Oral Tablet
  - prasugrel 10 MG Oral Tablet
  - rosuvastatin calcium 5 MG Oral Tablet
  - sodium fluoride 0.0272 MG/MG Oral Gel
  - ticagrelor 90 MG Oral Tablet
