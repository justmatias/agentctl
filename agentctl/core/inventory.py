from enum import StrEnum

from pydantic import BaseModel

from agentctl.domain import Binding, Extension


class InventoryClassification(StrEnum):
    ADOPTED = "adopted"
    NEEDS_REVIEW = "needs_review"
    UNMANAGED = "unmanaged"


class InventoryItem(BaseModel):
    extension: Extension
    binding: Binding
    classification: InventoryClassification
