# main.py
import uuid
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from langgraph.types import Command

from app.workflow import workflow
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Invoice LangGraph Agent")

# Stores intermediate results for manager review workflow
workflow_sessions = {}


class ManagerDecision(BaseModel):
    approve: bool
    comment: Optional[str] = None


# ============================================================
# PROCESS INVOICE
# ============================================================
@app.post("/process_invoice")
async def process_invoice(invoice_file: UploadFile = File(...), finance_email: str = None):

    # Read invoice file
    file_bytes = await invoice_file.read()

    print("\n===== DEBUG: RAW UPLOADED FILE =====")
    print("Filename:", invoice_file.filename)
    print("Content type:", invoice_file.content_type)
    print("Bytes length:", len(file_bytes))
    print("====================================\n")

    content_type = invoice_file.content_type

    # Create separate thread for workflow
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Initial workflow state
    initial_state = {
        "file_bytes": file_bytes,
        "content_type": content_type,
        "finance_email": finance_email,
        "thread_id": thread_id
    }

    # Run workflow until manager interruption
    result = None
    for event in workflow.stream(initial_state, config=config, stream_mode="values"):
        result = event

    # ------------ CRITICAL FIX ------------
    # Remove raw bytes because FastAPI cannot JSON-encode bytes
    if "file_bytes" in result:
        del result["file_bytes"]
    # --------------------------------------

    # Save state in memory for later manager approval
    workflow_sessions[thread_id] = result

    # If manager approval needed
    if "manager_decision" not in result or result["manager_decision"] is None:
        return {
            "status": "MANAGER_REVIEW_REQUIRED",
            "thread_id": thread_id,
            "analyzed": result.get("analyzed")
        }

    # If workflow finished (rare on first pass)
    return {"status": "COMPLETED", "result": result}


# ============================================================
# MANAGER DECISION → Resume workflow
# ============================================================
@app.post("/manager_decision/{thread_id}")
async def manager_decision(thread_id: str, decision: ManagerDecision):

    if thread_id not in workflow_sessions:
        raise HTTPException(404, "Thread not found")

    # Create resume command for LangGraph
    resume_cmd = Command(resume={
        "approve": decision.approve,
        "comment": decision.comment
    })

    config = {"configurable": {"thread_id": thread_id}}

    # Resume workflow from interrupt
    result = None
    for event in workflow.stream(resume_cmd, config=config, stream_mode="values"):
        result = event

    # ------------ CRITICAL FIX ------------
    # Remove raw bytes before returning JSON
    if "file_bytes" in result:
        del result["file_bytes"]
    # --------------------------------------

    workflow_sessions[thread_id] = result

    return {"status": "COMPLETED", "result": result}


# ============================================================
# RUN SERVER
# ============================================================
if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
