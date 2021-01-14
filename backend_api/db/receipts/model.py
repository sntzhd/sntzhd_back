from pydantic import Field
from typing import Dict, Optional, Any
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


class PersonalInfoDB(BaseDBModel):
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str
