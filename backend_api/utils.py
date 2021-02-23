from typing import TYPE_CHECKING, Dict
import inject
from datetime import datetime
from uuid import uuid4
import requests
from fastapi import Request
from fastapi_users.models import BaseUserDB
from pydantic import BaseModel, UUID4, Field
from uuid import UUID

from typing import Type, TypeVar

from backend_api.static_data import aliases, url_streets
from backend_api.entities import ReceiptEntity



T = TypeVar('T')


def instance(cls: Type[T]) -> T:
    inst: cls = inject.instance(cls)
    if TYPE_CHECKING:
        assert isinstance(inst, cls)
    return inst


def create_id():
    return uuid4()


def now():
    return datetime.utcnow()


def send_sms(phone: str, code: str):
    pass


def make_payer_id() -> str:
    pass


def get_payee_inn():
    pass


def get_alias_info(alias_name: str) -> Dict[str, str]:
    return aliases.get(alias_name)


def get_street_id(receipt: ReceiptEntity) -> str:
    street_id = None

    r_streets = requests.get(url_streets)

    for snt in r_streets.json()['sntList']:
        if snt.get('alias') == receipt.alias:
            for street in snt.get('streetList'):
                if street.get('strName') == receipt.street:
                    street_id = street.get('strID')
    return street_id

def get_street_id_by_name(alias: str, stret_name: str):
    r_streets = requests.get(url_streets)

    for snt in r_streets.json()['sntList']:
        if snt.get('alias') == alias:
            for street in snt.get('streetList'):
                if street.get('strName') == stret_name:
                    street_id = street.get('strID')
                    return street_id


def get_streets() -> str:
    r_streets = requests.get(url_streets)
    return r_streets

class PersonalInfoDB(BaseModel):
    id: UUID = Field(default_factory=create_id)
    user_id: UUID4
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str
    first_name: str
    last_name: str
    grand_name: str

async def on_after_register(user: BaseUserDB, request: Request):
    from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO, IDelegateDAO,
                                        IDelegateEventDAO, ICheckingNumberDAO)
    personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)
    print(f"User {user.id} has registered.")

    print(aliases.get('sntzhd'))
    #collection = db["personal_info"]
    #print(dir(collection))
    #personal_info = await collection.find(dict(user_id=user.id))
    #print(personal_info)

    street_id = get_street_id_by_name('sntzhd', user.street)

    payer_id = '{}-{}-{}'.format(aliases.get('sntzhd').get('payee_inn')[4:8], street_id, user.numsite)
    await personal_info_dao.create(PersonalInfoDB(**user.dict(), user_id=user.id, street_name=user.street,
                                                  snt_alias='sntzhd', payer_id=payer_id))
    print('on_after_register')
