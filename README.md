# AuditBot — Runtime Security Auditing for RAG Agents

CS6170 Course Project | Northeastern University MSAI 2025 | Mengqi Hao

AuditBot is a three-agent RAG pipeline with a multi-layer runtime security system that detects and blocks indirect prompt injection, data poisoning, PII exfiltration, and recipient hijacking attacks — without modifying the underlying LLM.

---

## Architecture

```
User Query
    │
    ▼
PlannerAgent → RetrieverAgent → SynthesizerAgent
       │               │                │
       └───────────────┴────────────────┘
                       │
                   AuditBot
         ┌─────────────────────────┐
         │  Semantic Drift Check   │  ← chain + question-anchor
         │  Action Param Integrity │  ← recursive scan + recipient strip
         │  Shadow + PII Verifier  │  ← Presidio entity detection
         │  HITL Risk Classifier   │  ← Tier 1 auto / Tier 2 queue / Tier 3 block
         └─────────────────────────┘
```

---

## Defense Layers

| Layer | What It Catches |
|---|---|
| Semantic Drift (chain) | Data poisoning — off-topic KB content shifts embedding space |
| Question-Anchor Drift | Retriever content diverging from original query |
| Action Param Integrity | Injected recipients, foreign URLs in email body |
| Presidio PII Scan | PII exfiltration in report output and email body |
| HITL Tier Classification | Escalates or blocks based on shadow + param violations |

---

## Attack Scenarios

| ID | Attack Type | Defense That Catches It | Outcome |
|---|---|---|---|
| S1 | Clean baseline | — | Auto-approved |
| S2 | Extra recipient injection | Param check — recipient strip | Blocked (Tier 3) |
| S3 | Full recipient hijack | Param check — recipient strip | Blocked (Tier 3) |
| S4a | Data poisoning (KB replacement) | Chain drift detection | Suspended |
| S4b | Indirect semantic drift | Chain drift detection | Suspended |
| S5 | Silent PII exfiltration | Presidio PII scan | Queued (Tier 2) |
| S6 | System prompt override | Param check — recipient strip | Blocked (Tier 3) |
| S7 | Malicious tool call | *(known gap — no action whitelist)* | Executes (gap demo) |

---

## Setup

**Requirements**: Python 3.11+, a Gemini or OpenAI API key.

```bash
# 1. Clone and create virtualenv
git clone https://github.com/haomengqi00709/6170_project.git
cd 6170_project
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg

# 3. Configure environment
cp .env.example .env
# Edit .env — set LLM_PROVIDER and the corresponding API key
```

**`.env` keys**:

```
LLM_PROVIDER=gemini          # or openai
GEMINI_API_KEY=...           # if using Gemini
OPENAI_API_KEY=...           # if using OpenAI
SMTP_FROM_EMAIL=...          # optional — for real email delivery
SMTP_APP_PASSWORD=...        # optional — Gmail App Password
```

---

## Running Experiments

### Full scenario suite (8 scenarios)

```bash
python test_scenarios.py
```

Results saved to `test_results.json`.

### Ablation study (proves each defense layer is necessary)

```bash
python ablation_scenarios.py
```

Results saved to `ablation_results.json`. Each run disables one defense layer and re-runs the corresponding attack to verify the attack succeeds without that layer.

### Single query (interactive)

```bash
python main.py
```

---

## Project Structure

```
├── core/
│   ├── agent.py          — three-agent pipeline + AuditBot orchestration
│   ├── auditor.py        — SQLite audit log + drift detection
│   ├── shadow.py         — shadow verifier (overlap check + Presidio PII)
│   ├── hitl.py           — HITL tier classifier
│   ├── rbac.py           — role-based access control
│   ├── vectorstore.py    — ChromaDB wrapper with RBAC filtering
│   ├── llm.py            — Gemini / OpenAI API wrapper
│   ├── events.py         — EventBus for real-time step monitoring
│   └── tools/
│       ├── email_tool.py           — email execution (mock/SMTP)
│       └── mock_install_tool.py    — mock package installer (S7 gap demo)
├── data/raw/
│   ├── senior/personal_profile.txt     — confidential user profile (RBAC: senior)
│   ├── public/web_article.txt          — S2: extra recipient injection
│   └── attacks/
│       ├── attack_full_hijack.txt      — S3: full recipient hijack
│       ├── attack_semantic_drift.txt   — S4: quantum computing data poisoning
│       ├── attack_pii_body.txt         — S5: PII dump instruction
│       ├── attack_prompt_injection.txt — S6: IGNORE ALL PREVIOUS INSTRUCTIONS
│       └── attack_tool_call.txt        — S7: malicious install directive
├── test_scenarios.py     — end-to-end test runner
├── ablation_scenarios.py — ablation study runner
├── EXPERIMENTS.md        — full experiment documentation
└── PAPER_APPENDIX_MATERIALS.md — system prompts, payloads, logs, code listings
```

---

## Key Results

All attacks are blocked or escalated when defenses are fully active. Ablation experiments confirm each layer is individually necessary:

- Removing PII scan → S5 exfiltration succeeds silently (Tier 1 auto-approved)
- Removing param check → injected recipient receives email undetected
- Removing drift detection → data poisoning undetected by primary signal

See `EXPERIMENTS.md` for full event traces, drift scores, and ablation analysis.
