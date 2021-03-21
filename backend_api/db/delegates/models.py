from pydantic import Field, UUID4
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime
from enum import Enum

from backend_api.db.common import BaseDBModel


def now():
    return datetime.utcnow()



class VoteDelegateValues(str, Enum):
    value_for = 'value_for'
    value_against = 'value_against'
    value_abstained = 'value_abstained'


class VoteDelegateDB(BaseDBModel):
    user_id: UUID4
    delegate_id: UUID4
    vote_value: VoteDelegateValues
    vote_date: datetime = Field(default_factory=now)
