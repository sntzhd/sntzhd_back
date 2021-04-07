from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field
from decimal import Decimal
from typing import Optional, List
import requests


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