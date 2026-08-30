# ClauseGuard — Product Requirements Document

**Version:** 1.0  
**Date:** 2026  
**Author:** Waniya  
**Status:** In Progress

---

## 1. Problem Statement

People in Pakistan sign contracts, rental agreements, 
job offers, and NDAs without reading them carefully.
Critical clauses are hidden in legal jargon that most
people cannot understand.

**Real Examples:**
- Tenant signs rental agreement — security deposit 
  was non-refundable, found out after moving out
- Employee signs job offer — 6 month bond existed,
  discovered after joining
- Freelancer signs client contract — IP rights 
  transferred to client unknowingly

---

## 2. Solution

An AI-powered document analysis tool that:
- Accepts PDF uploads
- Automatically detects risky clauses
- Generates a risk score (0-100)
- Explains findings in simple English
- Allows follow-up questions about the document

---

## 3. Target Users

| User Type | Use Case |
|-----------|----------|
| Students | Review internship and job offers |
| Tenants | Understand rental agreements |
| Freelancers | Verify client contracts |
| Small Businesses | Check vendor agreements |

---

## 4. Core Features (MVP)

### F1: Document Upload
- Accept PDF files (max 10MB)
- Support scanned PDFs via OCR
- Validate file type and size

### F2: Risk Analysis
- Generate risk score (0-100)
- Classify risk level: LOW / MEDIUM / HIGH
- List specific warnings with explanations

### F3: AI Summary
- Plain English summary of document
- Clause-by-clause breakdown
- Key obligations and rights highlighted

### F4: Follow-up Chat
- User can ask questions about the document
- Context retrieved from document
- Conversation history maintained per session

---

## 5. Technical Architecture
User Browser
↓
FastAPI Backend (REST API)
↓
┌─────────────────────────────┐
│ Agent Layer │
│ LangGraph State Machine │
└─────────────────────────────┘
↓ ↓
PDF Processor Risk Scorer
(PyMuPDF + OCR) (Rules Based)
↓
Vector Store
(Qdrant Local)
↓
LLM Analysis
(Gemini Flash — Free Tier)


---

## 6. Tech Stack

| Component | Technology | Reason |
|-----------|------------|--------|
| Backend API | FastAPI | Async, fast, auto docs |
| Agent Framework | LangGraph | State machine for agents |
| PDF Parsing | PyMuPDF | Best Python PDF library |
| OCR | Tesseract | Free, runs locally |
| Embeddings | sentence-transformers | Free, no API needed |
| Vector Database | Qdrant (local mode) | Production grade, free |
| LLM | Gemini 1.5 Flash | Free tier available |
| Package Manager | UV | Fast, modern standard |

---

## 7. Project Folder Structure

ClauseGuard/
│
├── app/
│ ├── init.py
│ ├── main.py # FastAPI app entry point
│ ├── config.py # Environment & settings
│ │
│ ├── routes/
│ │ ├── init.py
│ │ ├── documents.py # Upload & analyze routes
│ │ └── chat.py # Follow-up chat routes
│ │
│ ├── services/
│ │ ├── init.py
│ │ ├── pdf_service.py # PDF text extraction
│ │ ├── vector_service.py# Qdrant vector operations
│ │ ├── risk_service.py # Risk scoring logic
│ │ └── agent_service.py # LangGraph agent
│ │
│ ├── models/
│ │ ├── init.py
│ │ └── schemas.py # Pydantic request/response models
│ │
│ └── prompts/
│ └── analysis.py # All LLM prompts
│
├── frontend/
│ └── index.html # Simple UI
│
├── tests/
│ ├── init.py
│ └── test_basic.py # Basic tests
│
├── uploads/ # Temporary PDF storage
├── .env # Secret keys (never push)
├── .env.example # Template for others
├── .gitignore # Files to ignore
├── PRD.md # This file
├── README.md # Project overview
└── pyproject.toml # UV dependencies


---

## 8. API Design

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/docs` | Auto API documentation |
| POST | `/api/documents/analyze` | Upload and analyze PDF |
| POST | `/api/chat/ask` | Ask follow-up question |
| GET | `/api/documents/{id}` | Get analysis by ID |

---

## 9. Risk Scoring Rules

| Clause Type | Risk Points |
|-------------|-------------|
| Non-refundable deposit | 25 |
| Auto-renewal clause | 20 |
| Short notice termination (≤7 days) | 20 |
| Unilateral right to modify terms | 18 |
| Hidden or additional charges | 12 |
| Automatic fee/rent increase | 10 |
| Liability waiver | 15 |
| Mandatory arbitration | 5 |
| **Max possible total** | **125** |

**Final Score Formula:**

score = (points_found / 125) × 100


---

## 10. MVP Scope

### In MVP:
- PDF upload and processing
- Risk score and warnings
- English summary
- Basic follow-up chat
- Simple frontend UI

### Out of MVP (Future):
- User authentication
- Document history
- Urdu language UI
- Mobile application
- Lawyer referral system
- Payment/subscription

---

## 11. Development Phases

| Phase | Tasks | Est. Time |
|-------|-------|-----------|
| 1 | Environment setup, folder structure | Day 1 |
| 2 | PDF processing service | Day 2-3 |
| 3 | Risk scoring service | Day 4 |
| 4 | Vector store setup | Day 5-6 |
| 5 | LangGraph agent | Day 7-9 |
| 6 | FastAPI routes | Day 10-11 |
| 7 | Frontend | Day 12-13 |
| 8 | Testing and deployment | Day 14 |

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| PDF processing time | < 30 seconds |
| Risk detection accuracy | > 85% on test documents |
| API response time | < 5 seconds |
| Supported PDF size | Up to 10MB |