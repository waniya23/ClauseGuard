# app/services/risk_service.py

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================

DOCUMENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "rental": [
        "tenant", "landlord", "lessor", "lessee",
        "rent", "lease", "premises", "property",
        "house rent", "shop rent", "monthly rent",
        "security deposit", "advance rent",
        "vacant possession", "eviction",
        "maintenance charges", "society charges",
        "electricity meter", "gas meter",
        "subletting", "sub-let"
    ],
    "employment": [
        "employee", "employer", "employment",
        "salary", "wages", "probation",
        "designation", "department",
        "eobi", "pessi", "gratuity",
        "provident fund", "annual leave",
        "casual leave", "medical leave",
        "increment", "appraisal",
        "reporting manager", "joining date",
        "termination", "resignation",
        "notice period", "full and final",
        "relieving letter", "experience letter",
        "code of conduct", "noc"
    ],
    "freelance": [
        "contractor", "client", "freelancer",
        "deliverables", "milestone", "invoice",
        "project", "scope of work",
        "payment schedule", "net 30", "net 60",
        "upfront payment", "advance payment",
        "final payment", "billing",
        "revision", "feedback", "approval",
        "deadline", "timeline", "handover",
        "source files", "ownership",
        "intellectual property", "portfolio"
    ],
    "nda": [
        "confidential", "non-disclosure",
        "proprietary", "trade secret",
        "confidentiality", "disclose",
        "receiving party", "disclosing party",
        "confidential information",
        "shall not disclose", "keep confidential",
        "return of information",
        "breach of confidentiality",
        "permitted disclosure",
        "need to know basis"
    ],
    "loan": [
        "borrower", "lender", "loan",
        "interest rate", "repayment",
        "collateral", "principal amount",
        "installment", "emi", "markup",
        "disbursement", "outstanding balance",
        "default", "overdue",
        "state bank", "sbp",
        "murabaha", "diminishing musharakah",
        "mortgage", "pledge", "hypothecation",
        "guarantor", "surety"
    ]
}

UNIVERSAL_RULES: dict[str, dict] = {
    "unilateral_termination": {
        "points": 25,
        "keywords": ["terminate immediately", "termination without notice", "immediate termination", "terminate without cause"],
        "warning": "Party can terminate without notice",
        "law": "Contract Act 1872"
    },
    "no_notice_period": {
        "points": 25,
        "keywords": ["7 days notice", "7-day notice", "without notice", "3 days notice", "24 hours notice"],
        "warning": "Notice period is dangerously short",
        "law": "Industrial Relations Act 2012"
    },
    "non_refundable_deposit": {
        "points": 22,
        "keywords": ["non-refundable", "not refundable", "deposit forfeited", "no refund"],
        "warning": "Deposit cannot be recovered",
        "law": "Contract Act 1872"
    },
    "unilateral_changes": {
        "points": 20,
        "keywords": ["reserves the right to modify", "may change terms", "at our discretion", "without prior notice", "may amend"],
        "warning": "Other party can change terms unilaterally",
        "law": "Contract Act 1872, Section 23"
    },
    "auto_renewal": {
        "points": 20,
        "keywords": ["automatically renew", "auto-renew", "automatic renewal", "deemed renewed", "shall automatically extend"],
        "warning": "Contract auto-renews without your action",
        "law": "Consumer Protection Principles"
    },
    "unlimited_liability_waiver": {
        "points": 18,
        "keywords": ["not liable", "no liability", "waive any claim", "at your own risk", "disclaim all liability"],
        "warning": "Other party waives all liability",
        "law": "Contract Act 1872"
    },
    "hidden_charges": {
        "points": 15,
        "keywords": ["additional charges", "as applicable", "maintenance charges", "service charges", "charges may apply"],
        "warning": "Hidden or unclear additional charges",
        "law": "Consumer Protection"
    },
    "mandatory_arbitration": {
        "points": 10,
        "keywords": ["arbitration only", "binding arbitration", "no court", "waive right to court"],
        "warning": "Cannot take disputes to court",
        "law": "Access to Justice"
    }
}

EMPLOYMENT_RULES: dict[str, dict] = {
    "salary_deduction": {
        "points": 22,
        "keywords": ["deduct from salary", "salary deduction", "withhold salary", "deduct from final settlement"],
        "warning": "Employer can deduct salary without consent",
        "law": "Payment of Wages Act 1936"
    },
    "training_bond": {
        "points": 22,
        "keywords": ["training bond", "bond period", "recovery of training cost", "training cost recovery"],
        "warning": "Training bond may be unenforceable",
        "law": "Contract Act 1872"
    },
    "non_compete": {
        "points": 20,
        "keywords": ["non-compete", "not compete", "restraint of trade", "shall not work for"],
        "warning": "Non-compete clauses void in Pakistan",
        "law": "Contract Act 1872, Section 27"
    },
    "unpaid_overtime": {
        "points": 20,
        "keywords": ["overtime without pay", "no overtime compensation", "extended hours without"],
        "warning": "Overtime without compensation",
        "law": "Factories Act 1934"
    },
    "long_probation": {
        "points": 15,
        "keywords": ["probation of 6 months", "6-month probation", "12 month probation", "one year probation"],
        "warning": "Probation exceeds standard 3 months",
        "law": "Industry Standard"
    }
}

RENTAL_RULES: dict[str, dict] = {
    "short_notice_eviction": {
        "points": 25,
        "keywords": ["7 days to vacate", "vacate immediately", "15 days notice to vacate"],
        "warning": "Eviction notice period too short",
        "law": "Rent Restriction Ordinance 1959"
    },
    "tenant_all_repairs": {
        "points": 15,
        "keywords": ["tenant responsible for all repairs", "all maintenance by tenant", "tenant shall repair all"],
        "warning": "Tenant liable for all repairs",
        "law": "Rent Restriction Ordinance 1959"
    },
    "landlord_entry_no_notice": {
        "points": 18,
        "keywords": ["landlord may enter at any time", "owner may enter without notice", "inspect without prior notice"],
        "warning": "Landlord can enter without notice",
        "law": "Tenant Right to Peaceful Enjoyment"
    }
}

FREELANCE_RULES: dict[str, dict] = {
    "broad_ip_assignment": {
        "points": 25,
        "keywords": ["all intellectual property", "assigns all rights", "work for hire", "client owns all work"],
        "warning": "Client claims all your work ownership",
        "law": "Contract Act 1872"
    },
    "no_kill_fee": {
        "points": 20,
        "keywords": ["no cancellation fee", "cancel at any time without payment", "terminate without compensation"],
        "warning": "No payment if client cancels",
        "law": "Standard Contract Practice"
    },
    "late_payment_terms": {
        "points": 15,
        "keywords": ["net 90", "net 60", "payment within 90 days", "60 days payment"],
        "warning": "Payment terms exceed 30 days",
        "law": "Standard Practice"
    }
}

LOAN_RULES: dict[str, dict] = {
    "acceleration_clause": {
        "points": 25,
        "keywords": ["full amount due immediately", "accelerate payment", "entire balance immediately due"],
        "warning": "Full loan due immediately on default",
        "law": "SBP Consumer Protection Guidelines"
    },
    "compound_interest": {
        "points": 22,
        "keywords": ["compound interest", "interest on interest", "compounded monthly", "compounded daily"],
        "warning": "Compound interest multiplies debt fast",
        "law": "SBP Guidelines"
    },
    "collateral_no_court": {
        "points": 25,
        "keywords": ["seize collateral without court", "repossess without court order", "take possession without legal process"],
        "warning": "Assets can be seized without court order",
        "law": "Pakistani Civil Law"
    }
}

NDA_RULES: dict[str, dict] = {
    "unlimited_duration": {
        "points": 22,
        "keywords": ["perpetual confidentiality", "indefinite period", "forever confidential", "in perpetuity", "no time limit"],
        "warning": "NDA duration unlimited — likely void",
        "law": "Contract Act 1872"
    },
    "unlimited_penalties": {
        "points": 20,
        "keywords": ["unlimited damages", "any and all damages without limitation"],
        "warning": "Penalties have no upper limit",
        "law": "Contract Act 1872"
    }
}

TYPE_RULES_MAP: dict[str, dict[str, dict]] = {
    "rental": RENTAL_RULES,
    "employment": EMPLOYMENT_RULES,
    "freelance": FREELANCE_RULES,
    "loan": LOAN_RULES,
    "nda": NDA_RULES,
    "general": {}
}

EMOJIS: dict[str, str] = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}

DOC_TYPE_LABELS: dict[str, str] = {
    "rental": "Rental Agreement",
    "employment": "Employment Contract",
    "freelance": "Freelance Contract",
    "nda": "Non-Disclosure Agreement (NDA)",
    "loan": "Loan Agreement",
    "general": "General Agreement"
}

SCALE_CONTEXT: dict[str, str] = {
    "low": "0-39: Generally safe to sign",
    "medium": "40-69: Review before signing",
    "high": "70-100: Seek legal advice first"
}

DISCLAIMER: str = (
    "This analysis is based on Pakistani contract law principles including "
    "Contract Act 1872, Industrial Relations Act 2012, Rent Restriction "
    "Ordinance 1959, Payment of Wages Act 1936, and SBP Guidelines. "
    "This is NOT a substitute for professional legal advice."
)


# ==========================================
# CORE ANALYSIS FUNCTIONS
# ==========================================

def detect_document_type(text: str) -> str:
    """Detects the document type based on keyword frequency score."""
    lowered_text = text.lower()
    scores = {}
    for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
        found = sum(1 for kw in keywords if kw in lowered_text)
        scores[doc_type] = found / len(keywords) if keywords else 0.0
    
    if not scores:
        return "general"
    
    best_type = max(scores, key=scores.get)
    return best_type if scores[best_type] >= 0.15 else "general"


def apply_rules(text: str, rules: dict[str, dict]) -> tuple[list[dict], int]:
    """Checks the text against given rules and returns triggered warnings and total score."""
    lowered_text = text.lower()
    warnings = []
    total_points = 0
    for rule_name, rule in rules.items():
        for kw in rule["keywords"]:
            if kw.lower() in lowered_text:
                warnings.append({
                    "clause": rule_name,
                    "warning": rule["warning"],
                    "points": rule["points"],
                    "law_reference": rule["law"],
                    "triggered_by": kw
                })
                total_points += rule["points"]
                break  # Stop checking other keywords for this rule once triggered
    return warnings, total_points


def get_advice(level: str, doc_type: str) -> str:
    """Returns tailored advice based on risk level and document type."""
    if level == "HIGH":
        advice_map = {
            "rental": "Do not sign. Contact a property lawyer.",
            "employment": "Negotiate terms before joining. Consult a labor lawyer.",
            "loan": "Seek financial and legal advice before borrowing.",
            "freelance": "Negotiate IP and payment terms first.",
            "nda": "Limit NDA scope and duration before signing."
        }
        return advice_map.get(doc_type, "Seek legal advice before signing.")
    if level == "MEDIUM":
        return "Review highlighted sections carefully."
    return "Standard agreement. Read all terms."


def analyze_document_risk(text: str) -> dict:
    """Orchestrates document risk analysis, combining universal and type-specific rules."""
    doc_type = detect_document_type(text)
    uni_warns, uni_pts = apply_rules(text, UNIVERSAL_RULES)
    type_warns, type_pts = apply_rules(text, TYPE_RULES_MAP.get(doc_type, {}))
    
    raw_points = uni_pts + type_pts
    max_pts = sum(r["points"] for r in UNIVERSAL_RULES.values()) + \
              sum(r["points"] for r in TYPE_RULES_MAP.get(doc_type, {}).values())
    
    score = min(100, int((raw_points / max_pts) * 100)) if max_pts > 0 else 0
    level = "HIGH" if score >= 70 else ("MEDIUM" if score >= 40 else "LOW")
    warnings = uni_warns + type_warns
    
    return {
        "score": score,
        "level": level,
        "level_emoji": EMOJIS.get(level, "🟢"),
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPE_LABELS.get(doc_type, "General Agreement"),
        "advice": get_advice(level, doc_type),
        "scale_context": SCALE_CONTEXT,
        "warnings": warnings,
        "total_issues": len(warnings),
        "legal_disclaimer": DISCLAIMER
    }
