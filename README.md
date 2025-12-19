# INVOICE ANOMALY DETECTION & APPROVAL AGENT

This project is a **FastAPI + LangGraph** powered invoice-processing workflow that ingests invoices (image/PDF), extracts structured data, detects anomalies using **pure LLM reasoning**, and integrates a **Human-in-the-Loop (HITL)** mechanism for manager approval before sending automated emails.

It demonstrates:
- OCR-based invoice extraction
- AI-driven anomaly detection
- Human approval workflow
- Automated finance & vendor email notifications
- Stateful workflow orchestration using LangGraph

---

## Features

1. **Invoice Upload**
   - Upload an invoice as an image or PDF.
   - OCR extracts raw invoice text.

2. **Invoice Extraction**
   - LLM converts OCR text into structured invoice JSON.
   - No hallucination or normalization of corrupted values.

3. **Invoice Anomaly Analysis**
   - LLM acts as a human auditor.
   - Detects issues such as:
     - Future invoice dates
     - Invalid or corrupted numeric fields
     - Missing required item fields
     - Price deviations (heuristic)
   - No strict arithmetic or Python-based validation.

4. **Invoice Summary Generation**
   - Separate LLM summarizes analyzer results.
   - Generates:
     - One-line anomaly summary
     - Severity & confidence
     - Finance email content
     - Vendor email content

5. **Manager Review (HITL)**
   - Workflow **pauses** for manager approval.
   - Manager approves or rejects the invoice.

6. **Conditional Workflow**
   - If approved → finance email is sent.
   - If rejected → vendor email is sent (if correction required).

7. **Automated Email Sending**
   - Emails sent via SMTP.
   - HTML invoice template used for finance notifications.

8. **Dataset Logging**
   - Each invoice item is appended to a CSV dataset.
   - Includes anomaly, severity, confidence, and manager decision.

9. **Session Management**
   - Each request has a unique `thread_id`.
   - Workflow state is checkpointed using `MemorySaver`.
   - Manager decisions resume the workflow without restarting.

---

## System Workflow

OCR → Invoice Extraction → Anomaly Analyzer → Summary Generator  
                                      ↓  
                               Manager Approval  
                                      ↓  
                              Email + Dataset Save

---

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Invoice_agent
```
2. Create Virtual Environment:
```bash
python -m venv venv
source venv/bin/activate  # (Linux/Mac)
venv\Scripts\activate     # (Windows)
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```
4. Configure Environment Variables:
```bash
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
PASSWORD=your_app_password
```
5. Running the application:
```bash
python main.py
```
**Open Swagger UI** 
http://127.0.0.1:8000/docs

## API Endpoints:
1. Upload invoice
```bash
POST /process_invoice
Content-Type: multipart/form-data
```
**Request:**
Upload an invoice image or PDF.

**Response (Manager Approval Required):**
```json
{
  "status": "MANAGER_REVIEW_REQUIRED",
  "thread_id": "abcd-1234",
  "parsed_invoice": { ... },
  "analyzed_summary": { ... }
}
```

2. Manager Decision
```bash
POST /manager_decision/{thread_id}
Content-Type: application/json
```
**Request:**
```bash
{
  "approve": true,
  "comment": "Looks fine"
}
```
**Response:**
```json
{
  "status": "COMPLETED",
  "thread_id": "abcd-1234",
  "result": { ... }
}
```

## Important Concepts
- Pydantic Models (InvoiceItem, AnalyzerResult, AnomalyResult)

- Ensure strict schema validation and safe LLM outputs.

- Human-in-the-Loop (HITL)

- Workflow pauses using interrupt().

- Manager input determines next path.

- No auto-approval without human confirmation.

- MemorySaver Checkpointer

- Preserves workflow state.

- Prevents re-running OCR or analysis after approval.

- Pure LLM Reasoning

- No hard-coded anomaly rules.

- No Python arithmetic for totals.

- Clean invoices are a valid outcome.

- Supported Anomalies (FUTURE_DATE, INVALID_NUMBER, MISSING_FIELD, PRICE_DEVIATION, TOTAL_MISMATCH)

- Design Principles

    - Analyzer output is the single source of truth

    - Summary agent never detects anomalies

    - No hallucination of missing data

    - Strict JSON-only LLM responses

    - Separation of reasoning and reporting agents






