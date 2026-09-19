"""Medical terminology table for peptide book retrieval.

Provides comprehensive drug/term → class/mechanism/condition mappings for
query expansion. Used by MedicalRetriever to cross-match medical terms
that vector similarity may miss.

Categories:
- Drug brand names (Ozempic, Wegovy, Mounjaro, Zepbound)
- Drug classes (GLP-1 agonist, GIP agonist, dual agonist, triple agonist)
- Medical conditions (diabetes, obesity, NAFLD, PCOS, osteoporosis)
- Mechanisms (gastric emptying, insulin secretion, appetite suppression)
- Side effects (nausea, pancreatitis, thyroid C-cell, gallbladder)
- Administration (subcutaneous, intravenous, oral, nasal)
- Regulatory terms (FDA, PCAC, NDA, ANDA, compounding, 503A, 503B)
- Grey-market terms (research chemical, compounding pharmacy, off-label)
- Peptide names (BPC-157, TB-500, CJC-1295, etc.)
"""

from __future__ import annotations

# Master terminology: term → list of related terms for query expansion
# Each entry maps a search term to related concepts that should boost
# retrieval when either appears in a query or document.
TERMINOLOGY_MAP: dict[str, list[str]] = {
    # ============================================================
    # Drug Brand Names → Generic names + classes
    # ============================================================
    "ozempic": ["semaglutide", "GLP-1 receptor agonist", "diabetes", "FDA approved"],
    "wegovy": ["semaglutide", "GLP-1 receptor agonist", "weight loss", "obesity", "FDA approved"],
    "mounjaro": ["tirzepatide", "GLP-1/GIP dual agonist", "diabetes", "FDA approved"],
    "zepbound": ["tirzepatide", "GLP-1/GIP dual agonist", "weight loss", "obesity", "FDA approved"],
    "rybelsus": ["semaglutide", "oral GLP-1", "oral peptide", "diabetes"],
    "victoza": ["liraglutide", "GLP-1 receptor agonist", "diabetes"],
    "saxenda": ["liraglutide", "GLP-1 receptor agonist", "weight loss", "obesity"],
    "trulicity": ["dulaglutide", "GLP-1 receptor agonist", "diabetes"],
    "bydureon": ["exenatide", "GLP-1 receptor agonist", "diabetes"],
    "byetta": ["exenatide", "GLP-1 receptor agonist", "diabetes"],
    "adlyxin": ["lixisenatide", "GLP-1 receptor agonist", "diabetes"],
    "symlin": ["pramlintide", "amylin analog", "diabetes"],
    # ============================================================
    # Drug Classes
    # ============================================================
    "glp-1 agonist": [
        "semaglutide",
        "liraglutide",
        "dulaglutide",
        "tirzepatide",
        "GLP-1 receptor agonist",
        "incretin",
    ],
    "glp-1 receptor agonist": [
        "semaglutide",
        "liraglutide",
        "dulaglutide",
        "tirzepatide",
        "GLP-1 agonist",
        "incretin",
    ],
    "gip agonist": ["tirzepatide", "retatrutide", "glucose-dependent insulinotropic polypeptide"],
    "dual agonist": ["tirzepatide", "zepbound", "mounjaro", "GLP-1/GIP", "twincretin"],
    "triple agonist": ["retatrutide", "GLP-1/GIP/glucagon"],
    "incretin": ["GLP-1 agonist", "GIP agonist", "semaglutide", "tirzepatide"],
    "ghrh analog": ["sermorelin", "cjc-1295", "tesamorelin", "growth hormone releasing hormone"],
    "gh secretagogue": ["ipamorelin", "growth hormone secretagogue", "ghrelin mimetic"],
    "amylin analog": ["pramlintide", "symlin"],
    "melanocortin agonist": ["melanotan", "pt-141", "bremelanotide"],
    # ============================================================
    # Medical Conditions
    # ============================================================
    "diabetes": [
        "type 2 diabetes",
        "semaglutide",
        "tirzepatide",
        "metformin",
        "insulin",
        "blood glucose",
        "HbA1c",
    ],
    "type 2 diabetes": ["semaglutide", "tirzepatide", "metformin", "insulin resistance", "obesity"],
    "obesity": [
        "semaglutide",
        "tirzepatide",
        "retatrutide",
        "weight loss",
        "BMI",
        "Wegovy",
        "Zepbound",
    ],
    "weight loss": [
        "semaglutide",
        "tirzepatide",
        "retatrutide",
        "obesity",
        "STEP trial",
        "SURMOUNT",
    ],
    "nafld": ["semaglutide", "non-alcoholic fatty liver disease", "liver", "metabolic syndrome"],
    "non-alcoholic fatty liver disease": [
        "semaglutide",
        "NAFLD",
        "liver fibrosis",
        "metabolic syndrome",
    ],
    "pcos": ["polycystic ovary syndrome", "metformin", "semaglutide", "insulin resistance"],
    "polycystic ovary syndrome": ["metformin", "semaglutide", "PCOS", "insulin resistance"],
    "osteoporosis": ["teriparatide", "Forteo", "bone density", "calcium"],
    "thyroid cancer": [
        "medullary thyroid cancer",
        "black box warning",
        "C-cell tumor",
        "semaglutide",
    ],
    "medullary thyroid cancer": ["black box warning", "thyroid C-cell", "semaglutide", "MEN2"],
    "pancreatitis": ["inflammation", "pancreas", "semaglutide", "tirzepatide", "safety warning"],
    "cardiovascular": ["heart disease", "SELECT trial", "MACE", "semaglutide", "stroke"],
    "sleep disorder": ["DSIP", "emideltide", "delta sleep-inducing peptide", "insomnia"],
    "insomnia": ["DSIP", "emideltide", "delta sleep-inducing peptide"],
    # ============================================================
    # Mechanisms of Action
    # ============================================================
    "gastric emptying": ["semaglutide", "tirzepatide", "GLP-1", "stomach", "nausea", "appetite"],
    "insulin secretion": ["semaglutide", "GLP-1", "pancreas", "beta cell", "glucose"],
    "appetite suppression": [
        "semaglutide",
        "tirzepatide",
        "GLP-1",
        "brain",
        "hypothalamus",
        "weight loss",
    ],
    "glucose dependent": [
        "semaglutide",
        "GLP-1",
        "insulin secretion",
        "glucose-dependent insulinotropic polypeptide",
    ],
    "beta cell": ["insulin secretion", "pancreas", "diabetes", "semaglutide"],
    "receptor agonist": ["GLP-1 receptor agonist", "semaglutide", "tirzepatide", "binding"],
    "hormone mimic": ["semaglutide", "GLP-1", "mimic", "natural hormone", "incretin"],
    "absorption enhancer": [
        "oral peptide",
        "oral semaglutide",
        "Rybelsus",
        "bioavailability",
        "intestinal lining",
    ],
    # ============================================================
    # Side Effects
    # ============================================================
    "nausea": [
        "semaglutide",
        "tirzepatide",
        "side effect",
        "gastric emptying",
        "vomiting",
        "tolerance",
    ],
    "vomiting": ["nausea", "semaglutide", "side effect", "gastric emptying"],
    "diarrhea": ["semaglutide", "tirzepatide", "side effect", "GI side effect"],
    "constipation": ["semaglutide", "side effect", "GI side effect"],
    "gallbladder": ["gallstones", "cholecystitis", "semaglutide", "tirzepatide", "side effect"],
    "gallstones": ["gallbladder", "cholelithiasis", "semaglutide", "weight loss"],
    "thyroid c-cell": [
        "black box warning",
        "thyroid cancer",
        "medullary thyroid cancer",
        "semaglutide",
        "rodent",
    ],
    "thyroid c-cell tumor": [
        "black box warning",
        "medullary thyroid cancer",
        "semaglutide",
        "rodent study",
    ],
    "hypoglycemia": ["low blood sugar", "insulin", "semaglutide", "diabetes medication"],
    "injection site": ["subcutaneous", "redness", "semaglutide", "tirzepatide", "reaction"],
    "muscle loss": ["sarcopenia", "weight loss", "lean mass", "semaglutide"],
    "sarcopenia": ["muscle loss", "aging", "growth hormone"],
    # ============================================================
    # Administration Routes
    # ============================================================
    "subcutaneous": ["injection", "semaglutide", "tirzepatide", "needle", "once weekly"],
    "intravenous": ["IV", "injection", "hospital", "direct bloodstream"],
    "oral": ["oral peptide", "oral semaglutide", "Rybelsus", "absorption enhancer", "pill"],
    "nasal": ["nasal spray", "intranasal", "peptide delivery", "absorption"],
    "topical": ["cream", "transdermal", "peptide", "skin"],
    "sublingual": ["under tongue", "dissolve", "absorption"],
    "intramuscular": ["IM injection", "deep muscle", "peptide"],
    "needle": ["injection", "subcutaneous", "syringe", "pen injector"],
    "pen injector": ["semaglutide pen", "Ozempic pen", "pre-filled pen"],
    "once weekly": ["semaglutide", "tirzepatide", "dulaglutide", "dosing schedule"],
    "daily injection": ["liraglutide", "Victoza", "Saxenda", "exenatide"],
    # ============================================================
    # Regulatory Terms
    # ============================================================
    "fda": ["Food and Drug Administration", "FDA approval", "NDA", "ANDA", "clinical trials"],
    "fda approval": ["FDA", "clinical trials", "NDA", "New Drug Application", "approved drug"],
    "fda approved": ["FDA approval", "NDA", "clinical evidence", "Phase 3"],
    "pcac": ["Pharmacy Compounding Advisory Committee", "recommendation", "non-binding", "FDA"],
    "nda": ["New Drug Application", "FDA approval", "Phase 3", "clinical trials"],
    "anda": ["Abbreviated New Drug Application", "generic", "FDA approval", "bioequivalence"],
    "phase 1": ["clinical trial", "safety testing", "dosing", "FDA"],
    "phase 2": ["clinical trial", "dosing", "efficacy", "FDA"],
    "phase 3": ["clinical trial", "efficacy", "thousands of patients", "FDA approval"],
    "clinical trials": ["Phase 1", "Phase 2", "Phase 3", "FDA approval", "evidence"],
    "clinical evidence": ["clinical trials", "Phase 3", "efficacy", "FDA approval"],
    "compounding": ["503A", "503B", "compounding pharmacy", "custom formulation", "pharmacy"],
    "503a": ["compounding pharmacy", "state board oversight", "custom prescription", "compounding"],
    "503b": ["outsourcing facility", "FDA registered", "bulk compounding", "compounding"],
    "compounding pharmacy": ["503A", "custom formulation", "compounding", "pharmacy"],
    "outsourcing facility": ["503B", "FDA registered", "bulk compounding"],
    "black box warning": ["FDA warning", "safety warning", "thyroid C-cell", "medication guide"],
    "medication guide": ["FDA required", "black box warning", "patient safety"],
    "off-label": ["not FDA approved for", "off label use", "prescribing", "physician discretion"],
    "off label": ["not FDA approved for", "off-label use", "prescribing"],
    "generic": ["ANDA", "bioequivalent", "generic drug", "FDA approved"],
    "bioequivalence": ["generic", "ANDA", "same effect", "FDA approval"],
    "abbreviated new drug application": ["ANDA", "generic drug", "FDA approval"],
    "new drug application": ["NDA", "FDA approval", "Phase 3", "clinical trials"],
    "animal only": ["not FDA approved", "research", "animal study", "experimental"],
    "not yet approved": ["experimental", "investigational", "Phase 3", "clinical trials"],
    "investigational": ["not FDA approved", "clinical trials", "experimental", "research"],
    # ============================================================
    # Grey-Market Terms
    # ============================================================
    "research chemical": [
        "grey market",
        "not for human consumption",
        "research only",
        "bypass FDA",
        "no human safety data",
    ],
    "research only": ["research chemical", "not for human consumption", "grey market"],
    "not for human consumption": [
        "research chemical",
        "grey market",
        "bypass FDA",
        "research only",
    ],
    "grey market": [
        "research chemical",
        "unregulated",
        "grey-market",
        "research peptide",
        "online vendor",
    ],
    "grey-market": ["research chemical", "grey market", "unregulated"],
    "unregulated": ["grey market", "research chemical", "no FDA oversight", "quality risk"],
    "online vendor": ["grey market", "research chemical", "unregulated", "website"],
    "unverified source": ["grey market", "research chemical", "quality risk", "contamination"],
    "contamination": ["grey market", "research chemical", "bacterial", "heavy metals", "purity"],
    "purity": [
        "grey market",
        "research chemical",
        "contamination",
        "quality",
        "third-party testing",
    ],
    "no human data": ["animal only", "research chemical", "experimental", "no safety data"],
    "peptide vendor": ["grey market", "research chemical", "online vendor"],
    "research peptide": ["grey market", "research chemical", "unregulated"],
    # ============================================================
    # Specific Peptide Drug Names
    # ============================================================
    "semaglutide": [
        "GLP-1 receptor agonist",
        "Ozempic",
        "Wegovy",
        "Rybelsus",
        "diabetes",
        "weight loss",
        "STEP trial",
    ],
    "tirzepatide": [
        "GLP-1/GIP dual agonist",
        "Mounjaro",
        "Zepbound",
        "diabetes",
        "weight loss",
        "SURMOUNT",
    ],
    "liraglutide": ["GLP-1 receptor agonist", "Victoza", "Saxenda", "diabetes", "weight loss"],
    "dulaglutide": ["GLP-1 receptor agonist", "Trulicity", "diabetes"],
    "exenatide": ["GLP-1 receptor agonist", "Byetta", "Bydureon", "diabetes"],
    "lixisenatide": ["GLP-1 receptor agonist", "Adlyxin", "diabetes"],
    "retatrutide": ["triple agonist", "GLP-1/GIP/glucagon", "weight loss", "not yet FDA approved"],
    "cjc-1295": ["GHRH analog", "growth hormone releasing hormone", "peptide", "grey market"],
    "sermorelin": ["GHRH analog", "growth hormone releasing hormone", "prescription peptide"],
    "tesamorelin": ["GHRH analog", "growth hormone releasing hormone", "HIV lipodystrophy"],
    "ipamorelin": ["GH secretagogue", "growth hormone secretagogue", "peptide"],
    "bpc-157": [
        "Body Protection Compound",
        "gastric peptide",
        "grey market",
        "research chemical",
        "animal study",
    ],
    "tb-500": ["thymosin beta-4", "synthetic peptide", "grey market", "wound healing"],
    "thymosin beta-4": ["TB-500", "synthetic peptide", "wound healing"],
    "dsip": ["Delta sleep-inducing peptide", "emideltide", "sleep peptide", "PCAC"],
    "emideltide": ["DSIP", "Delta sleep-inducing peptide", "sleep peptide"],
    "epitalon": ["telomerase activator", "peptide", "anti-aging", "grey market"],
    "mots-c": ["mitochondrial peptide", "mitochondria", "metabolic health", "grey market"],
    "melanotan": ["melanocortin receptor agonist", "tanning peptide", "grey market"],
    "pt-141": ["melanocortin receptor agonist", "bremelanotide", "sexual dysfunction"],
    "ziconotide": ["calcium channel blocker", "pain medication", "Prialt"],
    "teriparatide": ["Forteo", "osteoporosis", "bone density", "PTH analog"],
    "pramlintide": ["Symlin", "amylin analog", "diabetes"],
    "ghrh": ["growth hormone releasing hormone", "sermorelin", "cjc-1295", "GHRH analog"],
    "gip": [
        "glucose-dependent insulinotropic polypeptide",
        "tirzepatide",
        "retatrutide",
        "incretin",
    ],
    "glucagon": ["retatrutide", "glucagon receptor", "blood sugar", "liver"],
    "amylin": ["pramlintide", "glucose control", "diabetes"],
    "hcg": ["human chorionic gonadotropin", "pregnancy hormone", "weight loss protocol"],
    "hgh": ["human growth hormone", "somatotropin", "growth hormone"],
    "growth hormone": [
        "HGH",
        "sermorelin",
        "ipamorelin",
        "cjc-1295",
        "growth hormone releasing hormone",
    ],
    "insulin": ["peptide hormone", "diabetes", "blood glucose", "pancreas"],
    "oxytocin": ["peptide hormone", "love hormone", "social bonding"],
    "vasopressin": ["peptide hormone", "ADH", "antidiuretic"],
    "ghrelin": ["hunger hormone", "appetite", "growth hormone secretagogue"],
    "leptin": ["satiety hormone", "appetite suppression", "obesity"],
    "glp-1": ["GLP-1 receptor agonist", "semaglutide", "incretin", "GLP-1 agonist"],
    # ============================================================
    # Trial Names
    # ============================================================
    "step trial": ["semaglutide", "STEP 1", "weight loss", "14.9%", "68 weeks"],
    "step 1": ["semaglutide", "STEP trial", "14.9% weight loss", "68 weeks"],
    "select trial": ["semaglutide", "cardiovascular", "MACE", "20% reduction"],
    "surpass trial": ["tirzepatide", "semaglutide", "superior", "head-to-head"],
    "surmount trial": ["tirzepatide", "weight loss", "SURMOUNT-1", "diabetes"],
    # ============================================================
    # Storage & Stability Terms
    # ============================================================
    "refrigeration": ["cold storage", "peptide stability", "refrigerator", "temperature sensitive"],
    "peptide stability": ["refrigeration", "degradation", "temperature", "fragile", "cold chain"],
    "temperature sensitive": ["refrigeration", "heat degradation", "peptide stability"],
    "freeze-thaw": ["peptide stability", "degradation", "refrigeration", "denaturation"],
    "cold chain": ["refrigeration", "shipping", "temperature controlled"],
    "degradation": ["peptide stability", "heat", "refrigeration", "denatured"],
    "expiry": ["expiration date", "shelf life", "peptide stability"],
    "shelf life": ["expiration", "storage", "peptide stability"],
    # ============================================================
    # Safety & Risk Terms
    # ============================================================
    "contraindication": ["should not take", "warning", "safety", "precaution"],
    "side effect": ["adverse effect", "reaction", "nausea", "vomiting", "safety"],
    "adverse effect": ["side effect", "reaction", "safety", "adverse event"],
    "drug interaction": ["interaction", "contraindication", "medication interaction"],
    "pregnancy risk": ["contraindication", "pregnancy", "Category X", "teratogenic"],
    "teratogenic": ["birth defect", "pregnancy risk", "contraindicated in pregnancy"],
    "overdose": ["toxicity", "excessive dose", "emergency"],
    "allergic reaction": ["hypersensitivity", "anaphylaxis", "allergy"],
    "long-term safety": [
        "long term effects",
        "chronic use",
        "safety data",
        "post-market surveillance",
    ],
    "post-market surveillance": ["long-term safety", "Phase 4", "FDA monitoring"],
    # ============================================================
    # Delivery Technology
    # ============================================================
    "liposomal": ["delivery system", "encapsulation", "bioavailability"],
    "nanoparticle": ["delivery system", "targeted delivery", "bioavailability"],
    "microneedle": ["transdermal delivery", "patch", "painless injection"],
    "microsphere": ["sustained release", "depot injection", "extended release"],
    "sustained release": ["extended release", "depot", "long-acting"],
    "bioavailability": ["absorption", "oral peptide", "delivery", "first-pass metabolism"],
    # ============================================================
    # Peptide Types
    # ============================================================
    "signaling peptide": ["messenger", "cellular communication", "peptide hormone"],
    "structural peptide": ["collagen", "keratin", "structural protein"],
    "antimicrobial peptide": ["AMP", "defensin", "antibacterial peptide", "immune defense"],
    "neuropeptide": ["brain peptide", "neurotransmitter", "CNS peptide"],
    "cyclopeptide": ["cyclic peptide", "stable peptide", "constrained peptide"],
    "peptide hormone": [
        "signaling molecule",
        "insulin",
        "oxytocin",
        "glucagon",
        "peptide messenger",
    ],
    # ============================================================
    # General Medical Terms
    # ============================================================
    "diagnosis": ["medical diagnosis", "condition", "identified", "symptoms"],
    "treatment": ["therapy", "medication", "management", "intervention"],
    "prognosis": ["outcome", "expected course", "outlook"],
    "etiology": ["cause", "origin", "pathogenesis"],
    "pathophysiology": ["disease mechanism", "physiological process"],
    "mechanism of action": ["MOA", "how it works", "pharmacology", "receptor"],
    "pharmacology": ["drug action", "mechanism", "pharmacokinetics", "pharmacodynamics"],
    "efficacy": ["effectiveness", "how well it works", "clinical trial"],
    "half-life": ["elimination", "duration", "pharmacokinetics"],
    "clearance": ["elimination", "pharmacokinetics", "metabolism"],
    "contraindicated": ["should not be used", "warning", "risk"],
    "monotherapy": ["single drug", "alone", "not combination"],
    "combination therapy": ["combination", "dual therapy", "multi-drug"],
    "first-line treatment": ["initial therapy", "standard of care", "primary treatment"],
    "evidence level": ["clinical evidence", "Phase 3", "RCT", "case report"],
    "randomized controlled trial": ["RCT", "clinical evidence", "gold standard", "Phase 3"],
    "placebo": ["control group", "sugar pill", "sham treatment"],
    "double-blind": ["blinded study", "neither knows", "bias reduction"],
    "peer review": ["published research", "scientific validation", "journal"],
    "meta-analysis": ["systematic review", "pooled data", "evidence synthesis"],
    # ============================================================
    # Book Structure Terms
    # ============================================================
    "book author": ["Author A", "Author B", "author", "front matter"],
    "author a": ["author", "healthcare writer", "technology writer", "book author"],
    "author b": ["author", "MD", "physician", "book author"],
    "edition": ["version", "fourth edition", "2026", "published"],
    "table of contents": ["contents", "chapters", "book structure"],
    "glossary": ["definitions", "terminology", "back matter"],
    "reference": ["citation", "bibliography", "sources"],
    "appendix": ["supplementary", "back matter", "claims register"],
    "claims register": ["evidence table", "reference table", "appendix"],
    "dosage": ["dose", "how much", "amount", "mg", "milligram"],
    "dose": ["dosage", "amount", "mg", "administration"],
    "mg": ["milligram", "dosage", "amount"],
    "milligram": ["mg", "dosage"],
    "ml": ["milliliter", "volume", "injection"],
    "injection": ["subcutaneous", "needle", "shot", "pen injector"],
    "syringe": ["injection", "needle", "draw up"],
    "prescription": ["prescribed", "physician", "pharmacy", "Rx"],
    "pharmacist": ["pharmacy", "dispense", "medication expert"],
    "physician": ["doctor", "MD", "prescriber", "healthcare provider"],
    "doctor": ["physician", "MD", "healthcare provider", "prescriber"],
    "healthcare provider": ["physician", "doctor", "nurse practitioner", "prescriber"],
    "clinic": ["medical office", "healthcare facility", "outpatient"],
    "hospital": ["medical center", "inpatient", "emergency room"],
    "lab test": ["blood work", "laboratory", "diagnostic test"],
    "blood work": ["lab test", "blood test", "laboratory results"],
    "imaging": ["X-ray", "MRI", "CT scan", "ultrasound", "radiology"],
}


def expand_query_with_terminology(query: str) -> list[str]:
    """Expand a medical query with related terms for better retrieval.

    For each term in the query that matches a terminology entry, add
    related terms to the expansion list. This helps BM25 and vector
    search cross-match between drug names, classes, conditions, and
    mechanisms.

    Args:
        query: The original query string.

    Returns:
        List of expanded query strings (original + variants).

    Example:
        expand_query_with_terminology("How does semaglutide work?")
        -> ["How does semaglutide work? GLP-1 receptor agonist mechanism of action",
            "How does semaglutide work? Ozempic Wegovy"]
    """
    q_lower = query.lower()
    expansions: list[str] = []

    # Find all matching terminology entries
    for term, related_terms in TERMINOLOGY_MAP.items():
        if term in q_lower:
            # Add expansion with related terms
            new_terms = [t for t in related_terms if t.lower() not in q_lower]
            if new_terms:
                expansions.append(f"{query} {' '.join(new_terms[:5])}")

    return expansions if expansions else [query]


def get_related_terms(term: str) -> list[str]:
    """Get related terms for a given medical term.

    Args:
        term: Medical term to look up.

    Returns:
        List of related terms, or empty list if not found.
    """
    return TERMINOLOGY_MAP.get(term.lower(), [])


def expand_tokens(tokens: list[str]) -> list[str]:
    """Expand a list of tokens with related terminology tokens.

    Used during query preprocessing to add semantic context to
    token-based retrieval.

    Args:
        tokens: List of query tokens.

    Returns:
        Expanded list of tokens (original + related).
    """
    expanded = list(tokens)
    seen = set(tokens)
    for token in tokens:
        for related in get_related_terms(token):
            for rt in related.split():
                rt_clean = rt.lower().strip()
                if rt_clean not in seen and len(rt_clean) >= 2:
                    expanded.append(rt_clean)
                    seen.add(rt_clean)
    return expanded


def get_drug_class(drug_name: str) -> str | None:
    """Get the drug class for a given drug name.

    Legacy function for backward compatibility.
    """
    related = TERMINOLOGY_MAP.get(drug_name.lower(), [])
    # Return the first term that looks like a drug class
    for term in related:
        if "agonist" in term or "analog" in term or "inhibitor" in term:
            return term
    return related[0] if related else None


# Legacy alias for backward compatibility
DRUG_TO_CLASS: dict[str, str] = {}
for _drug, _related in TERMINOLOGY_MAP.items():
    if any("agonist" in r or "analog" in r or "inhibitor" in r or "blocker" in r for r in _related):
        for r in _related:
            if "agonist" in r or "analog" in r or "inhibitor" in r or "blocker" in r:
                DRUG_TO_CLASS[_drug] = r
                break
