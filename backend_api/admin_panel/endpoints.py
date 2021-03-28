from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field
from decimal import Decimal
from typing import Optional

class ReceiptDataToAdmin(BaseModel):
    t1_current: Decimal = Field(alias='t1Current')
    t1_expense: Decimal = Field(alias='t1Expense')
    t2_current: Optional[Decimal] = Field(alias='t2Current')
    t2_expense: Optional[Decimal] = Field(alias='t2Expense')
    raw_string: str = Field(alias='rawString')
    numsite: str

router = APIRouter()

@router.get('/to-admin')
async def to_admin() -> ReceiptDataToAdmin:
    import random
    statuses = [True, False]
    counter_type = [1, 2]
    if random.choice(statuses):
        t1_current = random.randint(250, 3500)
        t1_expense = random.randint(250, 3500)
        t2_current = random.randint(250, 3500)
        t2_expense = random.randint(250, 3500)
        numsite = random.randint(1, 99)

        if random.choice(counter_type) > 1:
            raw_string = 'raw_purpose_string": "ЗА:10/12/2020;СУМ:2965.48;СИРЕНЕВАЯ {};ЕНИН В.А.;Т1 {}.0 (РАСХОД {}.0 КВТ),СИРЕНЕВАЯ УЛ.,ДОМ №{},ОПЛ. ЭЛЕКТРОЭНЕРГИИ ПО ДОГОВОРУ №10177'.format(numsite, t1_current, t1_expense, numsite)
            return ReceiptDataToAdmin(t1Current=t1_current, t1Expense=t1_expense, numsite=numsite, rawString=raw_string)
        else:
            raw_string = 'raw_purpose_string": "ЗА:10/12/2020;СУМ:2965.48;СИРЕНЕВАЯ {};ЕНИН В.А.;Т1 {}.0 (РАСХОД {}.0 КВТ),{} 19072.0 (РАСХОД {}.0 КВТ),СИРЕНЕВАЯ УЛ.,ДОМ №{},ОПЛ. ЭЛЕКТРОЭНЕРГИИ ПО ДОГОВОРУ №10177'.format(numsite, t1_current, t1_expense, t2_current, t2_expense, numsite)
            return ReceiptDataToAdmin(t1Current=t1_current, t1Expense=t1_expense, t2Current=t2_current, t2Expense=t2_expense, numsite=numsite, rawString=raw_string)
    else:
        t1_current = random.randint(250, 3500)
        t1_expense = random.randint(250, 3500)
        t2_current = random.randint(250, 3500)
        t2_expense = random.randint(250, 3500)

        t1_current2 = random.randint(250, 3500)
        t1_expense2 = random.randint(250, 3500)
        t2_current2 = random.randint(250, 3500)
        t2_expense2 = random.randint(250, 3500)
        numsite = random.randint(1, 99)

        if random.choice(counter_type) > 1:
            raw_string = 'raw_purpose_string": "ЗА:10/12/2020;СУМ:2965.48;СИРЕНЕВАЯ {};ЕНИН В.А.;Т1 {}.0 (РАСХОД {}.0 КВТ),СИРЕНЕВАЯ УЛ.,ДОМ №{},ОПЛ. ЭЛЕКТРОЭНЕРГИИ ПО ДОГОВОРУ №10177'.format(
                numsite, t1_current, t1_expense, numsite)
            return ReceiptDataToAdmin(t1Current=t1_current2, t1Expense=t1_expense2, numsite=numsite, rawString=raw_string)
        else:
            raw_string = 'raw_purpose_string": "ЗА:10/12/2020;СУМ:2965.48;СИРЕНЕВАЯ {};ЕНИН В.А.;Т1 {}.0 (РАСХОД {}.0 КВТ),{} 19072.0 (РАСХОД {}.0 КВТ),СИРЕНЕВАЯ УЛ.,ДОМ №{},ОПЛ. ЭЛЕКТРОЭНЕРГИИ ПО ДОГОВОРУ №10177'.format(
                numsite, t1_current, t1_expense, t2_current, t2_expense, numsite)
            return ReceiptDataToAdmin(t1Current=t1_current2, t1Expense=t1_expense2, t2Current=t2_current2, t2Expense=t2_expense2,
                                      numsite=numsite, rawString=raw_string)