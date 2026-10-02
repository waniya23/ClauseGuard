# 🛡️ ClauseGuard — AI Contract Risk Guardian (Pakistan Edition)

ClauseGuard is a production-grade, privacy-focused legal contract risk analysis tool designed specifically for Pakistani citizens (tenants, employees, freelancers, and borrowers). It uses a hybrid intelligence pipeline combining deterministic legal rule engines with Groq LLMs and local vector retrieval (RAG) to identify hidden traps, unfair obligations, and void clauses before you sign.

---

## ✨ Key Features

- **Multi-Format Ingestion**: Upload digital PDF documents or snap photos/screenshots directly on mobile (`.pdf`, `.png`, `.jpg`, `.jpeg`).
- **Zero-Install Vision OCR**: Automatically transcribes scanned documents and camera photos using **Groq Vision** (`llama-3.2-11b-vision-preview`) without requiring system-level Tesseract installations.
- **Hybrid Risk Scoring**:
  - *Phase 1*: Lightning-fast keyword rules scanning for Pakistani legal compliance (Contract Act 1872, Rent Restriction Ordinance 1959, Payment of Wages Act 1936).
  - *Phase 2*: Groq Llama 3.3 contextual reasoning to evaluate the real-world impact of flagged clauses.
- **Interactive Risk Gauge**: Dynamic visual score meter (0 to 100) with color-coded safety tiers:
  - 🟢 **LOW RISK (0-39)**: Generally safe standard agreement.
  - 🟡 **MEDIUM RISK (40-69)**: Caution recommended. Review flagged clauses.
  - 🔴 **HIGH RISK (70-100)**: Dangerous terms detected. Seek legal advice before signing.
- **Grounded Follow-Up Chat (RAG)**: Ask questions about your contract with answers strictly grounded in your text and cited with page numbers.
- **100% Free & Open-Source**: Zero cloud vector costs (Local Qdrant), zero embedding costs (FastEmbed CPU ONNX), and free Groq developer tier.

---

## 🛠️ Tech Stack

| Layer | Component | Details |
| :--- | :--- | :--- |
| **Backend** | FastAPI + Uvicorn | High-performance async REST API |
| **Agent Orchestration** | LangGraph | State machine pipeline tracking document lifecycle |
| **Document Processing** | PyMuPDF (`fitz`) | PDF parsing, normalization, and page rendering |
| **Vision OCR** | Groq Vision | `llama-3.2-11b-vision-preview` for scanned contracts |
| **Embeddings** | FastEmbed | `BAAI/bge-small-en-v1.5` on local CPU via ONNX (~67MB) |
| **Vector DB** | Qdrant Local | Persistent local vector store in `./qdrant_data/` with `doc_id` isolation |
| **LLM Inference** | Groq | `llama-3.3-70b-versatile` (Temperature 0.1) |
| **Frontend** | HTML5 / Tailwind CSS / Lucide | Mobile-first responsive UI with direct camera support |
| **Package Manager** | UV | Ultra-fast Python package management |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.13+
- [UV Package Manager](https://github.com/astral-sh/uv)
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 2. Setup Environment
Clone the repository and set up your `.env` file:
```powershell
cp .env.example .env
```
Open `.env` and add your Groq key:
```env
GROQ_API_KEY=gsk_your_actual_key_here
DEBUG=False
```

### 3. Install Dependencies
```powershell
uv sync
```

### 4. Run the Application
Start the FastAPI server:
```powershell
uv run uvicorn app.main:app --reload
```
Open your browser at **[http://localhost:8000](http://localhost:8000)** to view the dashboard!

---

## 🧪 Running Automated Tests

Run the test suite:
```powershell
uv run pytest tests/test_basic.py
```

---

## 📜 Legal Disclaimer
ClauseGuard provides educational risk analysis based on general Pakistani contract law principles. It is **not** a substitute for formal legal representation or professional legal advice.
