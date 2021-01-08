from pydantic import BaseModel, Field
from backend_api.utils import create_id
from uuid import UUID

class BaseDBModel(BaseModel):
    id: UUID = Field(default_factory=create_id)
