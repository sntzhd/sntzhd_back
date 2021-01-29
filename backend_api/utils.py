from typing import TYPE_CHECKING, Dict
import inject
from datetime import datetime
from uuid import uuid4
import requests

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
