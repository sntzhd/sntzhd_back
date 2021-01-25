from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from enum import Enum
from datetime import datetime


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
    t1_current: Decimal
    t1_paid: Decimal
    t2_current: Optional[Decimal]
    t2_paid: Optional[Decimal]
    service_name: Services
    numsite: str
    counter_image_id: Optional[str]
    alias: Optional[str]

class PersonalInfoEntity(BaseModel):
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str

class ListResponse(BaseModel):
    items: List[BaseModel]
    count: int

class OldReceiptEntity(BaseModel):
    qr_string: str
    first_name: str
    last_name: str
    grand_name: str
    payer_address: str
    purpose: str
    street: str
    counter_type: int
    rashod_t1: int
    rashod_t2: int
    result_sum: Optional[str]
    status: PayStatus = PayStatus.new.value
    service_name: Services
    payer_id: str
    img_url: str
    created_date: datetime
    bill_qr_index: str
    counter_image_id: Optional[str]
    t1_current: int
    t1_expense: Optional[str]
    t1_sum: Optional[str]
    numsite: Optional[str]
    last_name_only: Optional[str]
    t1_paid: Optional[str]
    t1_current: Optional[str]
    t2_paid: Optional[str]
    t2_current: Optional[str]
