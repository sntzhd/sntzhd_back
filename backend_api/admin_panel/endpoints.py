from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field
from decimal import Decimal
from typing import Optional, List, Any
import requests

from backend_api.interfaces import IRDataDAO
from backend_api.utils import instance
from backend_api.db.receipts.model import RDataDb

r_dao: IRDataDAO = instance(IRDataDAO)

class ReceiptDataToAdmin(BaseModel):
    t1Current: Decimal
    t1Expense: Decimal
    t1Paid: Decimal
    t2Current: Decimal
    t2Expense: Decimal
    t2Paid: Decimal
    t1Sum: str
    t2Sum: str
    proved: bool
    street_name: str
    numsite: str
    serviceName: str
    payment_sum: str
    counterType: str
    purpose_num_arr: List[str]
    purpose_num_name_arr: List[str]
    Onec_doc_hash: str
    raw_purpose_string: str
    payer_hash: str
    payment_date: str


router = APIRouter()


@router.get('/to-admin')
async def to_admin() -> ReceiptDataToAdmin:
    r = requests.get('https://next.json-generator.com/api/json/get/4klwLvrVq')
    print(r.json()[0])
    return ReceiptDataToAdmin(**r.json()[0], Onec_doc_hash=r.json()[0].get('1c_doc_hash'))


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
    t2Current: Decimal
    t2Expense: Optional[Decimal]
    t2Paid: Optional[Decimal]
    Sum: Decimal

@router.post('/to-admin-save')
async def to_admin_save(rq: RDataRq):
    await r_dao.create(RDataDb(**rq.dict()))