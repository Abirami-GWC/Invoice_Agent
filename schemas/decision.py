from pydantic import BaseModel

class ManagerDecision(BaseModel):
    approve: bool
    comment: str | None = None
