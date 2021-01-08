from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from enum import Enum


class PayStatus(str, Enum):
    new = 'new'
    paid = 'paid'

class Services(str, Enum):
    new = 'electricity'

class ReceiptEntity(BaseModel):
    name: str
    personal_acc: str
    bank_name: str
    bic: str
    corresp_acc: str
    kpp: str
    payee_inn: str
    first_name: str
    last_name: str
    grand_name: str
    payer_address: str
    purpose: str
    street: str
    counter_type: int
    rashod_t1: int
    rashod_t2: int
    result_sum: Optional[Decimal]
    t1_current: int
    t1_paid: int
    service_name: Services
    numsite: str
    counter_image_id: Optional[str]

class PersonalInfoEntity(BaseModel):
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str

class ListResponse(BaseModel):
    items: List[BaseModel]
    count: int
