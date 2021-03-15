import re
import requests
from typing import Dict, Any, List
from decimal import Decimal
import datetime
from pydantic.error_wrappers import ValidationError
import hashlib

from config import remote_service_config
from backend_api.utils import get_alias_info
from backend_api.entities import RawReceipt, RawReceiptCheck


def perhaps_house_number(value: str, sreet_name: str):
    space_params = value.split(' ')
    comma_params = value.split(',')
    house_number_is_next_param = False

    for param in comma_params:

        if house_number_is_next_param:
            try:
                return str(int(param))
            except ValueError:
                pass

        if len(re.findall(r'{}'.format(sreet_name), param.lower())) > 0:

            if len(param) == len(sreet_name):
                house_number_is_next_param = True

            if len(param) > len(sreet_name):
                if len(param.split(' ')) > 1:
                    try:
                        l = param.split(' ')
                        v = [l[(len(l) - 1)]]
                        return str(int(v[0]))
                    except ValueError:
                        pass

    # print('comma_params NO', space_params)

    if len(space_params) == 1:
        if len(space_params[0].split(',')) == 1:
            return space_params[0].split(',')[0].lower().split(sreet_name)[1]
        if len(space_params[0].split(',')) == 2:
            try:
                return int(space_params[0].split(',')[1])
            except ValueError:
                if len(re.findall('\d+[а-яё]{1}', space_params[0].split(',')[1].lower())) > 0:
                    return re.findall('\d+[а-яё]{1}', space_params[0].split(',')[1].lower())[0]
                else:
                    if len(re.findall('\d+', space_params[0].split(',')[1].lower())) > 0:
                        return re.findall('\d+', space_params[0].split(',')[1].lower())[0]

    is_street = False
    for v in value.split(' '):
        if len(re.findall(r'{}'.format(sreet_name), v.lower())) > 0:
            is_street = True

        if is_street:
            if len(re.findall('\d+[а-яё]{1}', v.lower())) > 0:
                is_street = False
                return re.findall('\d+[а-яё]{1}', v.lower())[0]
            else:
                if len(re.findall('\d+', v.lower())) > 0:
                    is_street = False
                    return re.findall('\d+', v.lower())[0]


class PayerIdChecker:
    def __init__(self):
        self.payer_id_makes = [self.make_payer_id_1, self.make_payer_id_2]
        self.dict_streets = None
        self.key_id_dict_streets = None
        self.alias = None
        self.street_list = None

    def get_receipt_type(self, value: str):
        return None

    def get_alias(self):
        if self.alias is None:
            self.alias = get_alias_info('sntzhd')
        return self.alias

    def make_dict_streets(self):
        if self.dict_streets is None:
            dict_streets = dict()
            key_id_dict_streets = dict()

            r = requests.get(remote_service_config.street_list_url)

            street_list = r.json().get('sntList')[0].get('streetList')

            for street in street_list:
                dict_streets.update({street.get('strName').lower(): street.get('strID')})
                key_id_dict_streets.update({street.get('strID'): street.get('strName').lower()})
            self.dict_streets = dict_streets
            self.key_id_dict_streets = key_id_dict_streets
            return self.dict_streets
        else:
            return self.dict_streets

    def make_payer_id_1(self, raw_str: str):
        params = raw_str.split(';')
        street_numer = None
        house_number = None

        for param in params:
            street = self.get_coincidence_street(param)
            if street:
                street_numer = street.get('street_number')
                house_number = perhaps_house_number(param, street.get('street_name'))
                break

        if street_numer and house_number:
            alias: Dict[Any, Any] = self.get_alias()
            payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_numer, house_number)
            return payer_id

    def make_payer_id_2(self, raw_str: str):
        pass

    def check_payer_id(self, payer_id: str):
        if payer_id:
            a, b, c = payer_id.split('-')
            if len(payer_id.split('-')) == 3:
                try:
                    int(a)
                    int(b)
                    return True
                except ValueError:
                    pass
        return False

    def get_payer_id(self, raw_str: str):
        for payer_id_maker in self.payer_id_makes:
            payer_id = payer_id_maker(raw_str)
            if payer_id:
                return payer_id

    def get_coincidence_street(self, param: str):
        dict_streets = self.make_dict_streets()

        for k in dict_streets.keys():
            if len(re.findall(r'{}'.format(k), param.lower())) > 0:
                return dict(street_name=k, street_number=dict_streets.get(k))

    def get_street_name_by_id(self, payer_id: str):
        key_id_dict_streets = dict()
        stn, street_id, home = payer_id.split('-')
        if self.key_id_dict_streets is None:
            r = requests.get(remote_service_config.street_list_url)

            street_list = r.json().get('sntList')[0].get('streetList')

            for street in street_list:
                key_id_dict_streets.update({street.get('strID'): street.get('strName').lower()})
            self.key_id_dict_streets = key_id_dict_streets

        return self.key_id_dict_streets.get(int(street_id))

    def get_street_list(self):
        if self.street_list is None:
            r = requests.get(remote_service_config.street_list_url)
            street_list = r.json().get('sntList')[0].get('streetList')
            self.street_list = street_list
        return self.street_list



def raw_receipts_creator_by_file():
    raw_receipts: List[RawReceipt] = []

    f = open('1c_document_utfSAVE.txt')

    is_doc = False

    raw_date_received = None
    raw_purpose_payment = None
    raw_payer = None
    title_receipt_hash = None
    raw_amount = None

    for line in f:

        result = re.findall(r'СекцияДокумент', line)

        if len(result) > 0:
            is_doc = True

        result = re.findall(r'КонецДокумента', line)

        if len(result) > 0:

            try:
                r = RawReceipt(date_received=raw_date_received, purpose_payment=raw_purpose_payment, payer=raw_payer,
                           amount=raw_amount, title_receipt_hash=title_receipt_hash)
                raw_receipts.append(r)
            except ValidationError:
                    pass


            raw_current_paeer_text = None
            raw_date_received = None
            raw_purpose_payment = None
            raw_payer = None
            raw_amount = None
            title_receipt_hash = None
            is_doc = False

        if is_doc:
            if line[:13] == 'ДатаПоступило':
                raw_date_received = datetime.datetime.strptime(line[14:].replace('\n', ''), '%d.%m.%Y')

            if line[:17] == 'НазначениеПлатежа':
                raw_purpose_payment = line[18:].replace('\n', '')
                result = hashlib.md5(raw_purpose_payment.encode())
                title_receipt_hash = result.hexdigest()

            if line[:11] == 'Плательщик1':
                raw_payer = line[12:].replace('\n', '')

            if line[:5] == 'Сумма':
                raw_amount = Decimal(line[6:])

    return raw_receipts


def make_houses_on_street(values: List[Any]):
    houses_on_street = dict()
    for receipt_check in values:
        org, street, house_number = receipt_check.payer_id.split('-')
        street_name = receipt_check.street_name

        if houses_on_street.get(street_name) is None:
            houses_on_street.update({street_name: [house_number]})
        else:
            if house_number not in houses_on_street.get(street_name):
                houses = houses_on_street.get(street_name)
                houses.append(house_number)
                houses_on_street.update({street_name: houses})
    return houses_on_street


def make_payments_on_street(values: List[Any]):
    payments_on_street = dict()
    for receipt_check in values:
        org, street, house_number = receipt_check.payer_id.split('-')
        street_name = receipt_check.street_name

        if payments_on_street.get(street_name) is None:
            payments_on_street.update({street_name: 1})
        else:
            payments_on_street.update({street_name: (payments_on_street.get(street_name) + 1)})
    return payments_on_street


def make_street_losses_sums_dict(values: List[RawReceiptCheck]):
    street_losses_sums_dict = dict()
    for raw_receipt_check in values:
        street_name = raw_receipt_check.street_name

        if raw_receipt_check.receipt_type and raw_receipt_check.receipt_type.service_name == 'losses':
            if street_losses_sums_dict.get(street_name.lower()):
                street_losses_sums_dict.update(
                    {street_name.lower(): (street_losses_sums_dict.get(street_name.lower()) + Decimal(
                        raw_receipt_check.paid_sum))})
            else:
                street_losses_sums_dict.update({street_name.lower(): Decimal(raw_receipt_check.paid_sum)})
    return street_losses_sums_dict


def make_street_membership_fee_sums_dict(values: List[RawReceiptCheck]):
    street_membership_fee_sums_dict = dict()
    for raw_receipt_check in values:
        street_name = raw_receipt_check.street_name
        if raw_receipt_check.receipt_type and raw_receipt_check.receipt_type.service_name == 'membership_fee':
            street_membership_fee_sum_value = street_membership_fee_sums_dict.get(street_name.lower())

            if street_membership_fee_sum_value:
                street_membership_fee_sums_dict.update(
                    {street_name.lower(): (street_membership_fee_sum_value + Decimal(raw_receipt_check.paid_sum))})
            else:
                street_membership_fee_sums_dict.update(
                    {street_name.lower(): street_membership_fee_sum_value})
    return street_membership_fee_sums_dict
