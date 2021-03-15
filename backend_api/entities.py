from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from enum import Enum
from datetime import datetime


class PayStatus(str, Enum):
    new = 'new'
    paid = 'paid'


class Services(str, Enum):
    electricity = 'electricity'
    losses = 'losses'
    membership_fee = 'membership_fee'
    consumption = 'consumption'
    losses_prepaid = 'losses.prepaid'
    memberfee2021h1 = 'memberfee2021h1'
    memberfee2021 = 'memberfee2021'


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
    checking_number: Optional[str]
    neighbour: Optional[str]


class PersonalInfoEntity(BaseModel):
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str
    name: str
    lastname: str
    grandname: str
    street: str
    home: str
    is_delegate: Optional[bool]


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


class ReceiptType(BaseModel):
    service_name: Optional[Services]
    counter_type: Optional[int]


class Neighbor(BaseModel):
    payer_id: str
    phone: str
    street_name: str
    numsite: str


class RawReceiptCheck(BaseModel):
    title: str
    test_result: bool
    payer_id: Optional[str]
    needHandApprove: bool
    receipt_type: Optional[ReceiptType]
    paid_sum: Decimal
    title_receipt_hash: str
    receipt_date: datetime
    street_name: str


class UndefoundClient(BaseModel):
    title: str
    payer_id: str
    paid_sum: str


class UndefinedClient(BaseModel):
    title: str
    payer_id: str
    paid_sum: Decimal


class StreetSumResp(BaseModel):
    street_name: str
    general_sum: Decimal
    electricity_sum: Decimal
    losses_sum: Decimal
    memberfee_sum: Decimal
    paymPeriod: Optional[str]
    street_home_qty: Optional[int]
    street_payment_qty: Optional[int]
    coordinates: List[List[str]] = []


class PayerIdSum(BaseModel):
    payer_id: str
    general_sum: Decimal
    losses_sum: Decimal


class ExpensePayItem(BaseModel):
    title: str
    pay_sum: Decimal


class RespChack1cV2(BaseModel):
    raw_receipt_check_list: List[RawReceiptCheck]
    undefined_clients: List[UndefinedClient]
    undefined_clients_count: int
    all_rows_count: int
    chacking_rows_count: int
    all_sum: Decimal
    sum_streets: List[StreetSumResp]
    payer_ids_sums: List[PayerIdSum]
    sum_streets_result: Decimal
    membership_fee_sum: Decimal
    losses_sum: Decimal
    expense_rows_count: int
    expense_list: List[ExpensePayItem]
    expense_sum: Decimal
    undefound_clients_count: int


class RawReceipt(BaseModel):
    date_received: Optional[datetime]
    purpose_payment: str
    payer: str
    amount: Decimal
    title_receipt_hash: str
