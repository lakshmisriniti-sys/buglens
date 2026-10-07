from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

# Only these exact values are allowed. Anything else gets rejected with a 422 error.
Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "in_progress", "resolved", "closed"]


class BugCreate(BaseModel):
    """What the client must send to create a bug."""
    title: str = Field(min_length=1, max_length=200)
    raw_report: str = ""
    priority: Priority = "medium"
    status: Status = "open"
    environment: str = ""
    steps: list[str] = []
    expected: str = ""
    actual: str = ""
    labels: list[str] = []
    assignee: str = ""


class BugUpdate(BaseModel):
    """For editing: every field is optional, so you only send what changed."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    priority: Optional[Priority] = None
    status: Optional[Status] = None
    environment: Optional[str] = None
    steps: Optional[list[str]] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    labels: Optional[list[str]] = None
    assignee: Optional[str] = None


class StructureRequest(BaseModel):
    """A messy bug report to send to the AI."""
    raw_report: str = Field(min_length=1, max_length=5000)


class AITicket(BaseModel):
    """The exact shape of a generated ticket.

    The AI is required to answer in this shape (structured outputs), and the
    demo-mode rules produce the same shape, so the rest of the app treats both alike.
    """
    title: str
    priority: Priority
    environment: str
    steps: list[str]
    expected: str
    actual: str
    labels: list[str]


class StructureResult(AITicket):
    """What /api/ai/structure returns: the ticket, plus who made it."""
    source: Literal["ai", "demo"]


class UserReport(BaseModel):
    """What a user sends from the public report page.

    strip_whitespace removes spaces at the ends first, so "     " can't sneak past min_length.
    """
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=5000)]


class LoginRequest(BaseModel):
    """What the login page sends."""
    password: str = Field(max_length=200)


class ReportReceipt(BaseModel):
    """What the user gets back: just a reference number."""
    id: int


class Bug(BugCreate):
    """What the API sends back: everything in BugCreate plus server-made fields."""
    id: int
    created_at: str
    updated_at: str
