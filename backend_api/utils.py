from typing import TYPE_CHECKING, Dict
import inject
from datetime import datetime
from uuid import uuid4
import requests
from fastapi import Request
from fastapi_users.models import BaseUserDB
from pydantic import BaseModel, UUID4, Field
from uuid import UUID
from urllib.parse import quote_plus

from backend_api.smsc_api import SMSC

from typing import Type, TypeVar

from backend_api.static_data import aliases, url_streets
from backend_api.entities import ReceiptEntity
from backend_api.interfaces import IPersonalInfoDAO

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
    personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)

    street_id = get_street_id_by_name('sntzhd', user.street)

    payer_id = '{}-{}-{}'.format(aliases.get('sntzhd').get('payee_inn')[4:8], street_id, user.numsite)
    await personal_info_dao.create(PersonalInfoDB(**user.dict(), user_id=user.id, street_name=user.street,
                                                  snt_alias='sntzhd', payer_id=payer_id))
    print('on_after_register')


def greensmsru_send_sms(phone, msg):
    """Отправка смс сообщения через сервис greensms.ru"""
    return False
    api_url = 'https://api3.greensms.ru/sms/send'
    params = {'user': 'sntzhdru',
              'pass': 'Tb709DWc',
              'to': phone,
              'txt': quote_plus(msg)}
    r = requests.get(api_url, params)
    if r.status_code != 200:
        print(r.status_code, r.reason)
        return None
    return r.json()


def smsru_send_sms(phone, msg):
    """Отправка смс сообщения через сервис sms.ru"""
    api_url = 'https://sms.ru/sms/send'
    params = {'api_id': 'BD780086-9A87-A775-27AA-B669FB4BF155',
              'to': phone,
              'msg': quote_plus(msg),
              'json': 1}
    r = requests.get(api_url, params)
    if r.status_code != 200:
        print(r.status_code, r.reason)
        return None

    sms_resp = r.json()

    if sms_resp:
        if sms_resp.get('sms'):
            return True

    return False


def smsc_send_sms(phone, msg):
    smsc = SMSC()

    r = smsc.send_sms(phone, msg, sender="sms")

    if len(r) == 2:
        if r[1] in ['-3', '-6', '-7']:
            return False
        else:
            return True
