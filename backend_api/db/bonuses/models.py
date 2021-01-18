from pydantic import Field, UUID4
from typing import Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

from backend_api.db.common import BaseDBModel


save_data = 'save_data'
transmission_testimony = 'transmission_testimony'
confirmation_payment = 'confirmation_payment'

bonus_values = dict(save_data=50, transmission_testimony=10, confirmation_payment=10)

def now():
    return datetime.utcnow()

class BonusAccDB(BaseDBModel):
    user_id: UUID4
    payer_id: str
    balls: int


class BonusType(str, Enum):
    save_data = save_data
    transmission_testimony = transmission_testimony
    confirmation_payment = confirmation_payment


class BonusHistoryDB(BaseDBModel):
    bonus_acc_id: UUID4
    bonus_type: BonusType
    created: datetime = Field(default_factory=now)

