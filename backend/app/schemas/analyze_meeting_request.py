from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeMeetingRequest(BaseModel):
    transcript: str = Field(min_length=1)
    model_id: UUID | None = None
