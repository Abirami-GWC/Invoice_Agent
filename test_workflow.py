from app.workflow3 import workflow

# prepare sample state
with open('debug/img.png','rb') as f:
    b = f.read()
state = {"file_bytes": b, "content_type": "image/png", "finance_email":"praviiabi@gmail.com"}

print("=== RUNNING AGENT WORKFLOW ===")
res = workflow.invoke(state)
print(res)
