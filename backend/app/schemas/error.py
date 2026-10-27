from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    error: str
    message: str
    details: dict[str, Any] | list[dict[str, Any]] | None = None
    path: str | None = None
    timestamp: datetime
