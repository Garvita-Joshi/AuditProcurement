"""Reusable, independently explainable audit control-point framework."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

class Category(str, Enum):
    STATISTICAL = "statistical"
    STRUCTURAL = "structural"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    RELATED_PARTY = "related_party"

class Status(str, Enum):
    FAIL_HIGH = "fail_high"
    FAIL_MEDIUM = "fail_medium"
    FAIL_LOW = "fail_low"
    PASS = "pass"

@dataclass
class ControlPointResult:
    control_point_id: str
    name: str
    description: str
    category: Category
    status: Status
    confidence: float
    explanation_text: str
    evidence: dict[str, Any] = field(default_factory=dict)

class ControlPoint(Protocol):
    id: str
    name: str
    description: str
    category: Category
    def evaluate(self, transaction: Any, ledger_context: list[Any]) -> ControlPointResult: ...

def result(control, status: Status, confidence: float, explanation: str, **evidence) -> ControlPointResult:
    return ControlPointResult(control.id, control.name, control.description, control.category, status,
                              round(max(0, min(100, confidence)), 1), explanation, evidence)
