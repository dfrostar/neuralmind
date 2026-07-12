"""
NeuralMind Market Intelligence & Financial Model Data
=====================================================
Synchronized data for PPTX, XLSX, and DOCX deliverables.
"""

# Market Data (sourced from Business Research Company, Mordor Intelligence, SNS Insider)
MARKET = {
    "current_size_2025": 7.65,  # USD B
    "projected_2030": 22.2,  # USD B
    "cagr": 0.238,
    "cloud_share_2025": 0.7247,
    "onprem_cagr": 0.2655,
    "enterprise_ai_2024": 24.0,  # USD B
    "gartner_2028_developer_adoption": 0.75,
    "developer_adoption_2025": 0.91,
    "code_generation_pct": 0.41,
    "ai_project_cancellation_2027": 0.40,
}

# Competitors
COMPETITORS = [
    {
        "name": "GitHub Copilot",
        "type": "Cloud IDE",
        "strength": "Largest user base",
        "weakness": "Vendor lock-in, MS dependency",
        "pricing": "$19-39/user/mo",
    },
    {
        "name": "Sourcegraph Cody",
        "type": "Enterprise Code Intelligence",
        "strength": "Multi-repo, deeply integrated",
        "weakness": "High cost, sales engagement",
        "pricing": "~$75K/year platform",
    },
    {
        "name": "Tabnine Enterprise",
        "type": "On-prem coding AI",
        "strength": "Privacy/air-gapped",
        "weakness": "Smaller ecosystem",
        "pricing": "Custom",
    },
    {
        "name": "AirgapAI",
        "type": "Local-first enterprise",
        "strength": "Compliance, SCIF certified",
        "weakness": "Newer, smaller market share",
        "pricing": "Custom",
    },
    {
        "name": "Continue.dev",
        "type": "OSS + Enterprise",
        "strength": "Open source, bring own LLM",
        "weakness": "Self-managed overhead",
        "pricing": "OSS free / Enterprise $20/user/mo",
    },
    {
        "name": "NeuralMind",
        "type": "Local-first Graph Intelligence",
        "strength": "Privacy, no code egress, open architecture",
        "weakness": "Smaller community, needs marketing",
        "pricing": "TBD",
    },
]

# Future-proofing Pillars
PILLARS = [
    "Local-First / Zero Code Egress",
    "Graph-Based Semantic Intelligence",
    "Open Architecture (no vendor lock-in)",
    "Self-Improving Synapse Layer",
    "Multi-Language Graph Parsing (tree-sitter/SCIP)",
    "Pluggable Vector Backends (ChromaDB/TurboVec)",
    "Enterprise SSO & RBAC",
    "Air-Gap / On-Premise Deployment",
    "Audit Trail & Compliance (SOC2/HIPAA)",
]

# Corporate Value Proposition
VALUE_PROP_ENGINEERING = [
    "On-device graph indexing — no code leaves the premise",
    "Semantic search across 8000+ node codebases",
    "Self-documenting via synapse learning",
    "Multi-language: Python, TS, Go, Rust, Java, C/C++",
    "IDE-agnostic via MCP protocol",
]

VALUE_PROP_BUSINESS = [
    "Engineering productivity metrics via audit trail",
    "Code knowledge persists through turnover",
    "Reduced onboarding time for new engineers",
    "Compliance: full data sovereignty",
    "Lower TCO vs cloud AI (no per-token API costs)",
]

# SWOT (abbreviated)
SWOT = {
    "strengths": [
        "Local-first privacy",
        "Graph-based intelligence",
        "Self-learning synapses",
        "Pluggable backends",
        "Open API",
    ],
    "weaknesses": [
        "Small community",
        "No enterprise sales team",
        "Limited IDE integrations",
        "Young codebase",
    ],
    "opportunities": [
        "$7.65B→$22.2B market",
        "Privacy regulations driving on-prem",
        "Enterprise AI adoption 91%",
        "Graph RAG unbundling from IDEs",
    ],
    "threats": [
        "GitHub Copilot network effects",
        "Sourcegraph enterprise lock-in",
        "Fragmented OSS alternatives",
        "Rapid model commoditization",
    ],
}

# Refactoring Priorities
REFACTOR_PRIORITIES = [
    {
        "item": "core.py decomposition",
        "impact": "HIGH",
        "effort": "MED",
        "rationale": "1811 lines, highest change surface",
    },
    {
        "item": "ir.py modularization",
        "impact": "HIGH",
        "effort": "LOW",
        "rationale": "963 lines, clear sub-modules",
    },
    {
        "item": "Remove regex-experiment.py",
        "impact": "MED",
        "effort": "LOW",
        "rationale": "Dangerous, unrecoverable source mutation",
    },
    {
        "item": "server.py decomposition",
        "impact": "MED",
        "effort": "MED",
        "rationale": "648 lines, mixed concerns",
    },
    {
        "item": "Remove deprecated enable_reranking",
        "impact": "LOW",
        "effort": "LOW",
        "rationale": "Dead attribute",
    },
]

# Financial Projections (5-year, conservative)
FINANCIAL = {
    "year_1": {"revenue": 0, "cost": 85000, "users": 0, "notes": "OSS launch, community building"},
    "year_2": {
        "revenue": 45000,
        "cost": 180000,
        "users": 50,
        "notes": "First enterprise pilots, 50 seats",
    },
    "year_3": {
        "revenue": 320000,
        "cost": 380000,
        "users": 250,
        "notes": "Enterprise tier launch, 10 paying teams",
    },
    "year_4": {
        "revenue": 950000,
        "cost": 620000,
        "users": 750,
        "notes": "Multi-region, partnership channel",
    },
    "year_5": {
        "revenue": 2400000,
        "cost": 1100000,
        "users": 2000,
        "notes": "Category leadership in local-first",
    },
}

# Pricing Model
PRICING = {
    "oss": {"price": "$0", "features": "Full graph intelligence, community support"},
    "team": {"price": "$25/user/mo", "features": "RBAC, audit trail, SSO, priority support"},
    "enterprise": {
        "price": "Custom (from $50K/yr)",
        "features": "Air-gap, SLA, custom parsers, dedicated CSM",
    },
}

# Target Segments
SEGMENTS = [
    {
        "name": "Engineering Teams (10-100)",
        "pain": "Copilot cost escalates, privacy concerns",
        "fit": "Team tier with RBAC",
    },
    {
        "name": "Security-Sensitive (Fintech, Defense)",
        "pain": "Cannot send code to cloud AI",
        "fit": "Enterprise air-gap deployment",
    },
    {
        "name": "Platform/Infra Teams",
        "pain": "Multi-repo complexity, onboarding cost",
        "fit": "Graph intelligence + audit trail",
    },
    {
        "name": "Business/Management",
        "pain": "Engineering productivity is a black box",
        "fit": "Dashboard + audit metrics",
    },
]
