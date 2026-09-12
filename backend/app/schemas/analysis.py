from typing import Any, Literal

from pydantic import BaseModel, Field

AnomalyClassification = Literal[
    "statistical_outlier",
    "logical_violation",
    "missing_data",
    "duplicate",
    "referential_inconsistency",
    "cross_column_inconsistency",
    "temporal_anomaly",
    "potential_business_anomaly",
    "confirmed_data_quality_issue",
    "unknown",
]
ConfidenceLevel = Literal["high", "medium", "low"]


class Finding(BaseModel):
    claim: str
    value: float | int | str | None = None
    unit: str | None = None
    affected_rows: int | None = None
    total_rows: int | None = None
    calculation: str | None = None
    classification: AnomalyClassification | None = None
    confidence: ConfidenceLevel = "medium"
    evidence: list[str] = Field(default_factory=list)
    # Set to False by app.ai.answer_validator when a finding's numbers
    # couldn't be matched to anything in the actual tool-call evidence —
    # never silently trusted just because the model said it.
    verified: bool = True


class ToolCallRecord(BaseModel):
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class ConversationTurn(BaseModel):
    question: str
    answer: str


class AnalyzeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=10)


class AnalyzeResponse(BaseModel):
    question: str
    answer: str
    findings: list[Finding] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    needs_clarification: str | None = None
    status: Literal["ok", "degraded"] = "ok"
    warnings: list[str] = Field(default_factory=list)
