from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel


class Indicator(BaseModel):
    name: str
    value: float
    signal: str
    metadata: Dict[str, Any]
    updated_at: datetime
