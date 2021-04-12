from pydantic import Field, UUID4
from typing import Dict, Optional, List, Any
from decimal import Decimal
from datetime import datetime

from backend_api.db.common import BaseDBModel
from backend_api.entities import PayStatus, Services


def now():
    return datetime.utcnow()


class ReceiptDB(BaseDBModel):
    qr_string: str
    #name: str
    #personal_acc: str
    #bank_name: str
    #bic: str
    #corresp_acc: str
    #kpp: str
    #payee_inn: str
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
    status: PayStatus = PayStatus.new.value
    service_name: Services
    payer_id: str
    img_url: str
    created_date: datetime = Field(default_factory=now)
    bill_qr_index: str
    counter_image_id: Optional[str]
    t1_current: int
    t1_expense: Optional[Decimal]
    t1_sum: Optional[Decimal]
    numsite: Optional[str]
    last_name_only: Optional[str]
    t1_paid: Optional[Decimal]
    t1_current: Optional[Decimal]
    t2_paid: Optional[Decimal]
    t2_current: Optional[Decimal]
    delegate_payer_id: Optional[str]


class PersonalInfoDB(BaseDBModel):
    user_id: UUID4
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str
    first_name: str
    last_name: str
    grand_name: str


class DelegateDB(BaseDBModel):
    user_id: UUID4
    payer_ids: List[str]


class DelegateEventDB(BaseDBModel):
    user_id: UUID4
    delegated_id: UUID4
    code: str


class CheckingNumberDB(BaseDBModel):
    value: str
    payer_id: str
    created_date: datetime = Field(default_factory=now)


class DelegatActionDB(BaseDBModel):
    delegated_id: UUID4
    payer_id: str
    receipt_id: UUID4

class RDataDb(BaseDBModel):
    counterType: int
    direction: str
    field_filled: int
    numsite: str
    pattern: str
    payer_hash: str
    payment_date: str
    purpose_num_arr: List[Any]
    raw_purpose_string: str
    serviceName: str
    street_name: str
    t1Current: Decimal
    t1Expense: Optional[Decimal]
    t1Paid: Optional[Decimal]
    t2Current: Optional[Decimal]
    t2Expense: Optional[Decimal]
    t2Paid: Optional[Decimal]
    Sum: Decimal
    proved: bool
