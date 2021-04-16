from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field, validator
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Any, Dict
import requests
from datetime import datetime

from backend_api.interfaces import IRDataDAO
from backend_api.utils import instance
from backend_api.db.receipts.model import RDataDb
from config import remote_service_config

r_dao: IRDataDAO = instance(IRDataDAO)

class ReceiptDataToAdmin(BaseModel):
    t1Current: Decimal
    t1Expense: Decimal
    t1Paid: Decimal
    t2Current: Optional[Decimal]
    t2Expense: Optional[Decimal]
    t2Paid: Optional[Decimal]
    t1Sum: Optional[str]
    t2Sum: Optional[str]
    proved: Optional[bool]
    street_name: str
    numsite: str
    serviceName: str
    payment_sum: str
    counterType: str
    purpose_num_arr: List[str]
    raw_purpose_string: str
    payer_hash: str
    payment_date: str
    proved: bool

    @validator('t2Current', pre=True, always=True)
    def check_t2_current(cls, v):
        try:
            Decimal(v)
            return v
        except InvalidOperation:
            return None

    @validator('t2Expense', pre=True, always=True)
    def check_t2_expense(cls, v):
        try:
            Decimal(v)
            return v
        except InvalidOperation:
            return None

    @validator('t2Paid', pre=True, always=True)
    def check_t2_paid(cls, v):
        try:
            Decimal(v)
            return v
        except InvalidOperation:
            return None


router = APIRouter()


@router.get('/to-admin')
async def to_admin(service_name: str = None, street: str = None, date_from: str = None, date_to: str = None) -> List[ReceiptDataToAdmin]:
    #r = requests.get('https://next.json-generator.com/api/json/get/4klwLvrVq')
    r = requests.get('https://functions.yandexcloud.net/d4ercvt5b4ad8fo9n23m')

    resp_list = []
    print(service_name, street, date_from, date_to)
    from pydantic.error_wrappers import ValidationError
    for r_raw in r.json():
        print(service_name, 'service_name')
        if service_name and r_raw.get('serviceName') != service_name:
            continue
        elif street and  r_raw.get('street_name').lower() != street.lower():
            continue
        elif date_from and date_to:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')

            if date_from_obj < date_to_obj:
                payment_date = datetime.strptime(r_raw.get('payment_date'), '%d.%m.%Y')
                if payment_date < date_from_obj or payment_date > date_to_obj:
                    print(date_from_obj, date_to_obj, payment_date)
                    continue

        try:
            r_raw_db = await r_dao.list(0, 1, dict(payer_hash=r_raw.get('payer_hash'), payment_date=r_raw.get('payment_date')))
            if r_raw_db.count > 0:
                proved = True
            else:
                proved = False
            resp_list.append(ReceiptDataToAdmin(**r_raw, payment_sum=r_raw.get('Сумма'), proved=proved))
        except ValidationError as e:
            pass
            #print(e)
    return resp_list
    #return ReceiptDataToAdmin(**r.json()[0], Onec_doc_hash=r.json()[0].get('1c_doc_hash'))


class RDataRq(BaseModel):
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

@router.post('/to-admin-save')
async def to_admin_save(rq: RDataRq):
    await r_dao.create(RDataDb(**rq.dict(), proved=True))

class StreetShort(BaseModel):
    strID: int
    strName: str

@router.get('/get-streets')
async def get_streets() -> List[StreetShort]:
    r = requests.get(remote_service_config.street_list_url)
    return [StreetShort(**street) for street in r.json().get('sntList')[0].get('streetList')]