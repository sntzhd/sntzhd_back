from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field
import requests
import datetime
from fastapi.responses import FileResponse
import weasyprint
import os
from fastapi.templating import Jinja2Templates
from starlette.responses import StreamingResponse
import io
import time
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi_users.password import get_password_hash
import calendar
import dateutil.relativedelta
from secrets import choice
import string
import base64
import json
import re
from decimal import Decimal, ROUND_FLOOR
import csv
import aiofiles
import hashlib
import codecs
import calendar
from enum import Enum

from backend_api.utils import instance, get_alias_info, get_street_id, get_streets
from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO, IDelegateDAO,
                                    IDelegateEventDAO, ICheckingNumberDAO, IDelegatActionDAO)
from backend_api.entities import (ListResponse, ReceiptEntity, PersonalInfoEntity, OldReceiptEntity, ReceiptType,
                                  Neighbor, RawReceiptCheck, UndefoundClient, RespChack1cV2, UndefinedClient,
                                  RawReceipt, StreetSumResp, PayerIdSum, ExpensePayItem)
from backend_api.db.receipts.model import (ReceiptDB, PersonalInfoDB, DelegateEventDB, DelegateDB, CheckingNumberDB,
                                           DelegatActionDB)
from backend_api.db.bonuses.models import BonusAccDB, BonusHistoryDB
from config import remote_service_config
from backend_api.db.motor.file import IFileDAO
from backend_api.db.exceptions import NotFoundError
from backend_api.services.auth_service.endpoints import user_db, UserDB
from backend_api.utils import create_id
from backend_api.smssend import send_sms
from backend_api.services.auth_service.endpoints import fastapi_users
from config import secret_config, run_backend_api_config
from backend_api.parser_utils import check_sum, get_addresses_by_hash
from backend_api.static_data import street_aliases, url_hauses_in_streets
from backend_api.static_data import aliases, url_streets
from backend_api.parser_v2_utils import (PayerIdChecker, raw_receipts_creator_by_file, make_houses_on_street,
                                         make_payments_on_street, make_street_losses_sums_dict,
                                         make_street_membership_fee_sums_dict)

router = APIRouter()

HISTORY_PAGE_SIZE = 20

receipt_dao: IReceiptDAO = instance(IReceiptDAO)
personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)
file_dao = instance(IFileDAO)
bonus_acc_dao = instance(IBonusAccDAO)
bonus_history_dao = instance(IBonusHistoryDAO)
delegate_dao = instance(IDelegateDAO)
delegate_event_dao = instance(IDelegateEventDAO)
checking_number_dao = instance(ICheckingNumberDAO)
delegat_action_dao: IDelegatActionDAO = instance(IDelegatActionDAO)

response_keys = dict(name='Name', personal_acc='PersonalAcc', bank_name='BankName', bic='BIC', corresp_acc='CorrespAcc',
                     kpp='KPP', payee_inn='PayeeINN', last_name='lastName', payer_address='payerAddress',
                     purpose='Purpose')

months = {
    1: 'Январь',
    2: 'Февраль',
    3: 'Март',
    4: 'Апрель',
    5: 'Май',
    6: 'Июнь',
    7: 'Июль',
    8: 'Август',
    9: 'Сентябрь',
    10: 'Октябрь',
    11: 'Ноябрь',
    12: 'Декабрь'
}

r_streets = requests.get(url_streets, verify=False)
raw_street_list = r_streets.json()['sntList'][0]['streetList']


class AliasInfoResp(BaseModel):
    name: str
    bank_name: str
    bic: str
    corresp_acc: str
    kpp: str
    payee_inn: str
    personal_acc: str


def get_work_key(k):
    wk = response_keys.get(k)

    if wk:
        return wk
    return k


class CreateReceiptResponse(BaseModel):
    img_url: str
    receipt: ReceiptDB
    formating_date: str
    formating_sum: str
    alias_info: AliasInfoResp


el_text = 'Оплата электроэнергии по договору №10177'
lose_text = 'ПОТЕРИ 15% СОГЛАСНО ПРОТОКОЛУ №9 ОТ 28.03.2015Г'


class User(BaseModel):
    id: UUID4
    username: str
    email: str
    is_active: bool
    is_superuser: bool


@router.post('/delegate-confirmation-rights', description='Проверка прав делегата')
async def delegate_confirmation_rights(receipt: ReceiptEntity) -> CreateReceiptResponse:
    print(receipt)


@router.post('/create-receipt', description='Создание квитанции')
async def create_receipt(receipt: ReceiptEntity,
                         user: User = Depends(fastapi_users.get_optional_current_active_user)) -> CreateReceiptResponse:
    if user == None:
        raise HTTPException(status_code=500, detail='Необходима автаризация')

    if receipt.neighbour:
        personal_infos = await personal_info_dao.list(0, 1, {'payer_id': receipt.neighbour})
    else:
        personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
    pinfo: PersonalInfoDB = personal_infos.items[0]

    receipt.first_name = pinfo.first_name
    receipt.last_name = pinfo.last_name
    receipt.grand_name = pinfo.grand_name
    receipt.street = pinfo.street_name
    receipt.payer_address = '{}, {}'.format(pinfo.street_name, pinfo.numsite)

    current_tariff = None

    alias = get_alias_info(receipt.alias)

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    street_id = get_street_id(receipt)

    # r_streets = requests.get(url_streets)

    # for snt in r_streets.json()['sntList']:
    #    if snt.get('alias') == receipt.alias:
    #        for street in snt.get('streetList'):
    #           if street.get('strName') == receipt.street:
    #               street_id = street.get('strID')

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, pinfo.numsite)

    payer_id = pinfo.payer_id

    # print(payer_id, "FFFFFFFFFFFFFF")
    # raise HTTPException(status_code=500, detail='Не верный alias')

    old_receipts = await receipt_dao.list(0, 1, {'payer_id': payer_id})

    # if user == None:
    #    raise HTTPException(status_code=500, detail='must_login')

    if old_receipts.count > 0:

        if receipt.checking_number:
            checking_numbers = await checking_number_dao.list(0, 1, {'value': receipt.checking_number,
                                                                     'payer_id': payer_id})
            if user:
                delegate_result = await delegate_dao.list(0, 1, {'user_id': user.id})

                if delegate_result.count == 0:
                    await delegate_dao.create(DelegateDB(user_id=user.id, payer_ids=[payer_id]))
                else:
                    if payer_id not in delegate_result.items[0].payer_ids:
                        delegate_result.items[0].payer_ids.append(payer_id)
                        await delegate_dao.update(delegate_result.items[0])
                        print('UPDATE')
                print('SAVE DELEGATE')

            if checking_numbers.count == 0:
                raise HTTPException(status_code=500,
                                    detail='Не верный код подтверждения. Попробуйте ввести его в поле Код подтверждения или начните сначала')
        else:

            personal_info_list = await personal_info_dao.list(0, 1, {'payer_id': payer_id})

            if user == None:
                password = ''.join([choice(string.digits) for _ in range(6)])
                print('CREATE checking_number', password)
                await checking_number_dao.create(CheckingNumberDB(value=password, payer_id=payer_id))
                raise HTTPException(status_code=500, detail='is_deligate')

            if personal_info_list.count > 0:
                if personal_info_list.items[0].user_id != user.id:
                    delegate_result = await delegate_dao.list(0, 1, {'user_id': user.id})

                    if delegate_result.count > 0:
                        if payer_id not in delegate_result.items[0].payer_ids:
                            password = ''.join([choice(string.digits) for _ in range(6)])
                            print('CREATE checking_number', password)
                            await checking_number_dao.create(CheckingNumberDB(value=password, payer_id=payer_id))
                            raise HTTPException(status_code=500, detail='is_deligate')

    receipt.name = alias.get('name')
    receipt.bank_name = alias.get('bank_name')
    receipt.bic = alias.get('bic')
    receipt.corresp_acc = alias.get('corresp_acc')
    receipt.kpp = alias.get('kpp')
    receipt.payee_inn = alias.get('payee_inn')
    receipt.personal_acc = alias.get('personal_acc')

    r = requests.get(remote_service_config.default_data_url)

    for tariff in r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs'):

        if current_tariff:
            if int(str(tariff.get('paymPeriod'))[-4:]) >= int(str(current_tariff.get('paymPeriod'))[-4:]) and int(
                    str(tariff.get('paymPeriod'))[:-4]) > int(str(current_tariff.get('paymPeriod'))[:-4]):
                current_tariff = tariff
        else:
            current_tariff = tariff

    current_tariff = r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs')[-1]

    receipts = await receipt_dao.list(0, HISTORY_PAGE_SIZE, {'payer_address': receipt.payer_address,
                                                             'service_name': receipt.service_name})

    if receipts.count > 0:
        if receipt.t1_current <= receipts.items[0].t1_current:
            pass
            # raise HTTPException(status_code=500,
            #                    detail='Ошибка # Не верное значение. Значение прошлого периода {} кВт'.format(
            #                        receipts.items[0].rashod_t1))

        if receipt.counter_type == 1:
            t1_sum = receipt.rashod_t1 * float(current_tariff.get('t0_tariff'))
        else:
            t1_sum = receipt.rashod_t1 * float(current_tariff.get('t1_tariff'))

        t2_sum = receipt.rashod_t2 * float(current_tariff.get('t2_tariff'))
        result_sum = t1_sum + t2_sum
        if receipt.service_name == 'losses':
            result_sum = result_sum * 0.15
    else:
        if receipt.counter_type == 1:
            t1_sum = receipt.rashod_t1 * float(current_tariff.get('t0_tariff'))
        else:
            t1_sum = receipt.rashod_t1 * float(current_tariff.get('t1_tariff'))

        t2_sum = receipt.rashod_t2 * float(current_tariff.get('t2_tariff'))
        result_sum = t1_sum + t2_sum
        if receipt.service_name == 'losses':
            result_sum = result_sum * 0.15

    # receipt.result_sum = int((result_sum * 100))
    receipt.result_sum = result_sum

    # receipt.payer_address = '{} {}'.format(receipt.street, receipt.payer_address)
    last_name_only = receipt.last_name
    receipt.last_name = '{} {} {}'.format(pinfo.last_name, pinfo.first_name, pinfo.grand_name)

    receipt.purpose = '{} '.format('|Phone={}'.format(pinfo.phone))

    if receipt.counter_type == 2:
        receipt.purpose = 'Т1 {} (расход {} кВт),'.format(receipt.t1_current, receipt.rashod_t1)

        t2p = 'Т2 {} (расход {} кВт)'.format(receipt.t2_current, receipt.rashod_t2,
                                             )
        receipt.purpose = '{}\n{}, {}, Л/С {}'.format(receipt.purpose, t2p,
                                                      el_text if receipt.service_name == 'electricity' else lose_text,
                                                      receipt.payer_address)
    else:
        receipt.purpose = 'Т {} (расход {} кВт), {}, Л/С {}'.format(receipt.t1_current, receipt.rashod_t1,
                                                                    el_text if receipt.service_name == 'electricity' else lose_text,
                                                                    receipt.payer_address)

    qr_string = ''

    for k in receipt.dict().keys():
        if k in response_keys.keys():
            if k == 'payer_address':
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))
            else:
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))

    # qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
    #                     k in response_keys.keys()])

    dt = datetime.datetime.now()

    paym_period = '{}{}'.format(dt.month, dt.year) if dt.day <= 10 else '{}{}'.format((dt.month - 1), dt.year)

    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}|PersAcc={}'.format(int((result_sum * 100)), paym_period, payer_id)

    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    img_url = qr_img.json().get('response').get('url')

    t1_expense = receipt.t1_current * receipt.t1_paid
    t1_sum = float(current_tariff.get('t0_tariff'))

    delegate_payer_id = None
    if receipt.neighbour:
        delegate_personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
        delegate_personal_info: PersonalInfoDB = delegate_personal_infos.items[0]
        delegate_payer_id = delegate_personal_info.payer_id

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=last_name_only, delegate_payer_id=delegate_payer_id))
    if receipt.neighbour:
        await delegat_action_dao.create(
            DelegatActionDB(delegated_id=user.id, payer_id=receipt.neighbour, receipt_id=id_))
    receipt = await receipt_dao.get(id_)

    try:
        sum_rub, sum_cop = str(receipt.result_sum).split('.')
    except ValueError:
        sum_rub = str(receipt.result_sum)
        sum_cop = '00'

    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=t1_expense, t1_sum=t1_sum,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(sum_rub, sum_cop[:2]),
                                 alias_info=AliasInfoResp(**alias))


@router.get('/receipts', description='Квитанции')
async def receipts(page: int = 0, street: str = None, start: str = None, end: str = None,
                   user=Depends(fastapi_users.get_current_user)):
    skip = page * HISTORY_PAGE_SIZE

    filters = dict()

    if street:
        filters.update({'street': street})

    if start and end:
        date_start_obj = datetime.datetime.strptime(start, '%Y-%m-%d')
        date_end_obj = datetime.datetime.strptime(end, '%Y-%m-%d')

        if date_end_obj > date_start_obj:
            filters.update({'created_date': {'$gte': date_start_obj, '$lte': date_end_obj}})

    receipts = await receipt_dao.list(skip, HISTORY_PAGE_SIZE, filters)
    return ListResponse(items=receipts.items, count=receipts.count)


@router.delete('/delete-receipt', description='Удаление квитанции')
async def delete_receipt(record_id: UUID4):
    # r = await receipt_dao.get(record_id)
    await receipt_dao.delete(record_id)
    # print(r)


@router.get('/get-pdf', description='Получить квитанцию в PDF формате')
async def get_pdf(request: Request, order_id: UUID4):
    templates = Jinja2Templates(directory="templates")

    r: ReceiptDB = await receipt_dao.get(order_id)

    try:
        sum_rub, sum_cop = str(r.result_sum).split('.')
    except ValueError:
        sum_rub = str(r.result_sum)
        sum_cop = '00'

    sntzhd = get_alias_info('sntzhd')
    print(r.img_url)
    add - losses - prepaid
    t = templates.TemplateResponse("receipt3.html",
                                   {"request": request, 'year': r.created_date.year,
                                    'month': months.get(r.created_date.month),
                                    'day': r.created_date.day, 'sum_rub': sum_rub, 'sum_cop': sum_cop[:2],
                                    'Sum': r.result_sum, 'Name': sntzhd.get('name'),
                                    'KPP': sntzhd.get('kpp'), 'PayeeINN': sntzhd.get('payee_inn'),
                                    'PersonalAcc': sntzhd.get('personal_acc'), 'BankName': sntzhd.get('bank_name'),
                                    'BIC': sntzhd.get('bic'),
                                    'qr_img': r.img_url,
                                    'CorrespAcc': sntzhd.get('corresp_acc'), 'КБК': '1', 'purpose': r.purpose,
                                    'payerAddress': r.payer_address, 'lastName': r.last_name, 'img_url': r.img_url}
                                   )
    pdf = weasyprint.HTML(string=str(t.body, 'utf-8')).write_pdf()
    open('order.pdf', 'wb').write(pdf)

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return FileResponse('{}/order.pdf'.format(BASE_DIR))


class OldValueResp(BaseModel):
    item: OldReceiptEntity
    count: int
    access_upload: bool


@router.get('/get-old-value', description='Предыдущие показания')
async def get_old_value(payer_address: str, user: User = Depends(fastapi_users.get_optional_current_active_user)):
    access_upload = False
    receipts = await receipt_dao.list(0, 1, {'payer_address': payer_address})
    if user != None:
        personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
        personal_info: PersonalInfoDB = personal_infos.items[0]

        if receipts.items[0].payer_id == personal_info.payer_id:
            access_upload = True

    receipts = await receipt_dao.list(0, 1, {'payer_address': payer_address})

    return OldValueResp(item=receipts.items[0], count=receipts.count, access_upload=access_upload)


@router.post('/save-pi', description='Сохранение данных платильщика')
async def save_pi(personal_info: PersonalInfoEntity) -> str:
    personal_infos = await personal_info_dao.list(0, 1, {'phone': personal_info.phone})

    # alias = aliases.get(personal_info.snt_alias)
    alias = get_alias_info(personal_info.snt_alias)

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    street_id = None

    r_streets = get_streets()

    for snt in r_streets.json()['sntList']:
        if snt.get('alias') == personal_info.snt_alias:
            for street in snt.get('streetList'):
                if street.get('strName') == personal_info.street_name:
                    street_id = street.get('strID')

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, personal_info.numsite)
    personal_info.payer_id = payer_id

    if personal_infos.count == 0:
        phone = personal_info.phone
        # if personal_info.phone[0] == '+':
        #    phone = personal_info.phone[1:]

        user_in_db = await user_db.get_by_email('{}@online.pay'.format(phone))

        if user_in_db == None:
            user_in_db = await user_db.create(UserDB(id=create_id(), hashed_password=get_password_hash('1111'),
                                                     email='{}@online.pay'.format(phone), name=personal_info.name,
                                                     lastname=personal_info.lastname, grandname=personal_info.grandname,
                                                     city='', street=personal_info.street, home=personal_info.home,
                                                     phone=personal_info.phone, payer_id=payer_id,
                                                     is_delegate=personal_info.is_delegate))

        if personal_info.phone[0] == '+':
            personal_info.phone = personal_info.phone[1:]

        await personal_info_dao.create(PersonalInfoDB(**personal_info.dict(), user_id=user_in_db.id))
        bonus_acc_dao = instance(IBonusAccDAO)
        bonus_history_dao = instance(IBonusHistoryDAO)

        id_ = await bonus_acc_dao.create(BonusAccDB(payer_id=payer_id, balls=50, user_id=user_in_db.id))
        await bonus_history_dao.create(BonusHistoryDB(bonus_acc_id=id_, bonus_type='save_data'))

    # else:
    #    user_in_db = await user_db.create(UserDB(id=create_id(), hashed_password=get_password_hash('1111'),
    #                                             email='{}@online.pay'.format(personal_info.phone), name='',
    #                                             lastname='', grandname='', city='', street='', home='',
    #                                             phone=personal_info.phone, payer_id=payer_id))
    #    personal_info_db = personal_infos.items[0]
    #   await personal_info_dao.delete(personal_info_db.id)
    #   await personal_info_dao.create(PersonalInfoDB(**personal_info.dict()))


@router.get('/get-receipt', description='Данные квитанции по ID')
async def get_receipt(receipt_id: UUID4):
    receipt: ReceiptDB = await receipt_dao.get(receipt_id)

    alias = get_alias_info('sntzhd')

    try:
        sum_rub, sum_cop = str(receipt.result_sum).split('.')
    except ValueError:
        sum_rub = str(receipt.result_sum)
        sum_cop = '00'

    return CreateReceiptResponse(img_url=receipt.img_url, receipt=receipt,
                                 alias_info=AliasInfoResp(**alias),
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(sum_rub, sum_cop[:2]))


@router.get('/get/{id_}', name='get_file')
async def file(
        id_: str,
) -> StreamingResponse:
    try:
        file_ = await file_dao.get(id_)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")

    etag = 'file-%s-%s-%s-%s' % (time.mktime(file_.uploadDate.timetuple()),
                                 file_.chunk_size, file_.filename, id_)

    return StreamingResponse(io.BytesIO(await file_.read()), media_type=file_.metadata.get('contentType'),
                             headers={'ETag': etag, 'Last-Modified': str(file_.uploadDate), 'Accept-Ranges': 'bytes',
                                      'Content-Length': str(file_.length)})


@router.post('/upload-image')
async def upload_image(file: UploadFile = File(...)) -> str:
    api = 'https://functions.yandexcloud.net/d4edmtn5porf8th89vro'

    im_b64 = base64.b64encode(file.file.read()).decode("utf8")

    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

    payload = json.dumps(
        {'request': {'image': im_b64}, 'function': 'image2bucket'})
    response = requests.post(api, data=payload, headers=headers)
    try:
        data = response.json()
        print(data)
        return data.get('response').get('unique')
    except requests.exceptions.RequestException:
        print(response.text)


@router.get('/change-status', description='Изменение статуса квитанции')
async def change_status(receipt_id: UUID4):
    receipt: ReceiptDB = await receipt_dao.get(receipt_id)

    personal_info = await personal_info_dao.list(0, 1, dict(payer_id=receipt.payer_id))

    bonus_acc = await bonus_acc_dao.list(0, 1, dict(user_id=personal_info.items[0].user_id))

    acc = bonus_acc.items[0]

    acc.balls += 10
    await bonus_acc_dao.update(acc)

    await bonus_history_dao.create(BonusHistoryDB(bonus_acc_id=acc.id, bonus_type='confirmation_payment'))

    receipt.status = 'paid'
    await receipt_dao.update(receipt)


class PayerInfo(BaseModel):
    snt: str
    streetName: str
    numsite: str
    lastname: str
    firstname: str
    grandname: str
    counterType: str
    t1Paid: Decimal
    t1Current: Decimal
    t2Paid: Optional[Decimal]
    t2Current: Optional[Decimal]
    bill_qr_index: str
    status: str
    service_name: str


@router.get('/find_payer_by_id', description='Поиск по платежному id')
async def change_status(payer_id: str) -> PayerInfo:
    receipts = await receipt_dao.list(0, 1, dict(payer_id=payer_id))

    if receipts.count > 0:
        receipt: ReceiptDB = receipts.items[0]
        return PayerInfo(snt='snt', streetName=receipt.street, numsite=receipt.numsite, lastname=receipt.last_name_only,
                         firstname=receipt.first_name, grandname=receipt.grand_name, counterType=receipt.counter_type,
                         t1Paid=receipt.t1_paid, t1Current=receipt.t1_current, t2Paid=receipt.t2_paid,
                         t2Current=receipt.t2_current, bill_qr_index=receipt.bill_qr_index, status=receipt.status,
                         service_name=receipt.service_name)


@router.get('/change_password', description='change_password')
async def change_password():
    password = '11111111'

    user_in_db = await user_db.get_by_email('user@example.com')

    user_in_db.hashed_password = get_password_hash(password)

    await user_db.update(user_in_db)


class FilterData(BaseModel):
    title: str
    start: str
    end: str


@router.get('/get-months')
async def get_months() -> List[FilterData]:
    resp_months = []

    dt = datetime.datetime.now()

    dt_month_last_day = calendar.monthrange(dt.year, dt.month)[1]
    current_df = FilterData(title=months.get(dt.month), start='{}-{}-{}'.format(dt.year, dt.month, 1),
                            end='{}-{}-{}'.format(dt.year, dt.month, dt_month_last_day))

    next_month = dt + dateutil.relativedelta.relativedelta(months=1)
    prev_month = dt - dateutil.relativedelta.relativedelta(months=1)

    next_df = FilterData(title=months.get(next_month.month),
                         start='{}-{}-{}'.format(next_month.year, next_month.month, 1),
                         end='{}-{}-{}'.format(next_month.year, next_month.month,
                                               calendar.monthrange(next_month.year, next_month.month)[1]))

    prev_df = FilterData(title=months.get(prev_month.month),
                         start='{}-{}-{}'.format(prev_month.year, prev_month.month, 1),
                         end='{}-{}-{}'.format(prev_month.year, prev_month.month,
                                               calendar.monthrange(prev_month.year, prev_month.month)[1]))

    resp_months.append(prev_df)
    resp_months.append(current_df)
    resp_months.append(next_df)

    return resp_months


class SendValidationSmsRq(BaseModel):
    phone: str


@router.post('/sendValidationSms')
async def send_validation_sms(rq: SendValidationSmsRq) -> str:
    if len(re.findall(r'@', rq.phone)) > 0:
        user_in_db = await user_db.get_by_email(rq.phone)
    else:
        user_in_db = await user_db.get_by_email('{}@online.pay'.format(rq.phone))
    print('UUSSS')
    print(rq.phone)
    print(rq.phone)
    if user_in_db == None:
        if rq.phone[0] == '+':
            user_in_db = await user_db.get_by_email('{}@online.pay'.format(rq.phone[1:]))
        else:
            user_in_db = await user_db.get_by_email('+{}@online.pay'.format(rq.phone))
    print(user_in_db)
    if user_in_db:

        if run_backend_api_config.DEV:
            password = '123456'
        else:
            password = ''.join([choice(string.digits) for _ in range(6)])
        user_in_db.hashed_password = get_password_hash(password)
        await user_db.update(user_in_db)

        if secret_config.SEND_SMS:
            send_sms_status = send_sms('7{}'.format(rq.phone.split('@')[0]), password)

            if send_sms_status == False:
                raise HTTPException(status_code=500, detail='Ошибка сервиса, код авторизации: {}'.format(password))
        else:
            print('NO SEND')
            print(password)

        return password
    else:
        raise HTTPException(status_code=403, detail='Нет в базе')


class BonusResp(BaseModel):
    balls: int
    history_bonus: List[BonusHistoryDB]


@router.get('/bonuses', description='Бонусы')
async def bonuses(page: int = 0, user=Depends(fastapi_users.get_current_user)):
    skip = page * HISTORY_PAGE_SIZE

    filters = dict(user_id=user.id)
    bonus_acc = await bonus_acc_dao.list(0, 1, filters)
    print(bonus_acc)

    acc = bonus_acc.items[0]

    history = await bonus_history_dao.list(skip, HISTORY_PAGE_SIZE, dict(bonus_acc_id=acc.id))

    resp = BonusResp(balls=acc.balls, history_bonus=history.items)
    return resp


class AddDelegateStartRQ(BaseModel):
    phone: str


class AddDelegateEndRQ(BaseModel):
    phone: str
    code: str


@router.post('/add-delegate-start')
async def add_delegate_start(rq: AddDelegateStartRQ, user=Depends(fastapi_users.get_current_user)) -> str:
    personal_infos = await personal_info_dao.list(0, 1, {'phone': rq.phone})
    print(personal_infos)

    if personal_infos.count == 0:
        raise HTTPException(status_code=500, detail='Нет в базе')
    else:
        p_info = personal_infos.items[0]
        code = ''.join([choice(string.digits) for _ in range(6)])
        id_ = await delegate_event_dao.create(DelegateEventDB(user_id=user.id, delegated_id=p_info.user_id, code=code))
        return id_


@router.post('/add-delegate-end')
async def add_delegate_end(rq: AddDelegateEndRQ, user=Depends(fastapi_users.get_current_user)) -> str:
    delegate_events = await delegate_event_dao.list(0, 1, dict(code=rq.code, user_id=user.id))
    if delegate_events.count == 0:
        raise HTTPException(status_code=500, detail='Не верный код')
    else:
        delegates = await delegate_dao.list(0, 1, dict(user_id=user.id))
        if delegates.count == 0:
            await delegate_dao.create(DelegateDB(user_id=user.id, client_ids=[delegate_events.items[0].delegated_id]))
        else:
            delegate = delegates.items[0]

            if delegate_events.items[0].delegated_id not in delegate.client_ids:
                delegate.client_ids.append(delegate_events.items[0].delegated_id)
                await delegate_dao.update(delegate)


@router.get('/delegates')
async def delegates(user=Depends(fastapi_users.get_current_user)) -> List[PayerInfo]:
    delegates = await delegate_dao.list(0, 1, dict(user_id=user.id))

    if delegates.count == 0:
        raise HTTPException(status_code=500, detail='Не делегат')

    delegate = delegates.items[0]
    personal_infos = await personal_info_dao.list(0, 1000, {'user_id': {'$in': delegate.client_ids}})
    return personal_infos.items


verification_data = ['ПОТЕР', '%', 'ЭЛЕКТРОЭНЕРГИИ', 'ПРОТОКОЛ', '15', 'ЭЛЕКТРО']
verification_data_lose = ['ПОТЕР', '%', 'ПРОТОКОЛ', '15']
verification_data_el = ['ЭЛЕКТРОЭНЕРГИИ', 'ЭЛЕКТРО']


def payment_destination_checker(value: str):
    for i in verification_data:
        result = re.findall(r'{}'.format(i), value)
        if len(result) > 0:
            return True
    return False


def payment_no_double_destination_checker(value: str):
    find_results = []

    for i in verification_data:
        result = re.findall(r'{}'.format(i), value)
        if len(result) > 0:
            find_results.append(i)

    if (len([find_result for find_result in find_results if find_result in verification_data_lose]) > 0 and len(
            [find_result for find_result in find_results if find_result in verification_data_el])):
        return False
    else:
        return True


class MembershipReceiptEntity(BaseModel):
    year: str
    neighbour: Optional[str]


@router.post('/add-membership-fee-2021')
async def add_membership_fee_2001(rq: MembershipReceiptEntity,
                                  user: User = Depends(fastapi_users.get_optional_current_active_user)):
    alias = get_alias_info('sntzhd')

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    if rq.neighbour:
        personal_infos = await personal_info_dao.list(0, 1, {'payer_id': rq.neighbour})
    else:
        personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
    pinfo: PersonalInfoDB = personal_infos.items[0]

    payd_sum = 2500
    payd_sum_qr_string = 250000
    text = 'Оплата членского взноса 2021'
    receipt = ReceiptEntity(name=alias.get('name'), bank_name=alias.get('bank_name'), bic=alias.get('bic'),
                            corresp_acc=alias.get('corresp_acc'), kpp=alias.get('kpp'),
                            payee_inn=alias.get('payee_inn'),
                            personal_acc=alias.get('personal_acc'), first_name=pinfo.first_name,
                            last_name='{} {} {}'.format(pinfo.last_name, pinfo.first_name, pinfo.grand_name),
                            grand_name=pinfo.grand_name,
                            payer_address='{}, {}'.format(pinfo.street_name, pinfo.numsite),
                            purpose='{} Л/C {}, {}'.format(text, pinfo.street_name, pinfo.numsite),
                            street=pinfo.street_name, counter_type=0, rashod_t1=0, rashod_t2=0, t1_current=0,
                            t1_paid=0, service_name='memberfee2021', numsite=pinfo.numsite)

    # qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
    #                     k in response_keys.keys()])

    qr_string = ''
    for k in receipt.dict().keys():
        if k in response_keys.keys():
            if k == 'payer_address':
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))
            else:
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))

    street_id = get_street_id(receipt)

    payer_id = pinfo.payer_id  # '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)
    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}|PersAcc={}'.format(payd_sum_qr_string, rq.year, payer_id)
    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)
    receipt.result_sum = payd_sum

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    img_url = qr_img.json().get('response').get('url')

    delegate_payer_id = None
    if rq.neighbour:
        delegate_personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
        delegate_personal_info: PersonalInfoDB = delegate_personal_infos.items[0]
        delegate_payer_id = delegate_personal_info.payer_id

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=receipt.last_name, delegate_payer_id=delegate_payer_id))

    if rq.neighbour:
        await delegat_action_dao.create(DelegatActionDB(delegated_id=user.id, payer_id=rq.neighbour, receipt_id=id_))

    receipt = await receipt_dao.get(id_)

    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=0, t1_sum=0,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(2500, '00'),
                                 alias_info=AliasInfoResp(**alias))


@router.post('/add-membership-fee')
async def add_membership_fee(rq: MembershipReceiptEntity,
                             user: User = Depends(fastapi_users.get_optional_current_active_user)):
    if user == None:
        raise HTTPException(status_code=500, detail='Необходима автаризация')

    alias = get_alias_info('sntzhd')

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    if rq.neighbour:
        personal_infos = await personal_info_dao.list(0, 1, {'payer_id': rq.neighbour})
    else:
        personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
    pinfo: PersonalInfoDB = personal_infos.items[0]

    if rq.year == '2021h1':
        payd_sum = 1250
        payd_sum_qr_string = 125000
        text = 'Оплата членского взноса 1 полугодие 2021. На выплату задолженности перед АО НЭСК (оферта auditsnt.ru/nesk)'
        receipt = ReceiptEntity(name=alias.get('name'), bank_name=alias.get('bank_name'), bic=alias.get('bic'),
                                corresp_acc=alias.get('corresp_acc'), kpp=alias.get('kpp'),
                                payee_inn=alias.get('payee_inn'),
                                personal_acc=alias.get('personal_acc'), first_name=pinfo.first_name,
                                last_name='{} {} {}'.format(pinfo.last_name, pinfo.first_name, pinfo.grand_name),
                                grand_name=pinfo.grand_name,
                                payer_address='{}, {}'.format(pinfo.street_name, pinfo.numsite),
                                purpose='{} {} Л/C {}, {}'.format(text, '|Phone={}'.format(pinfo.phone), pinfo.street_name, pinfo.numsite),
                                street=pinfo.street_name, counter_type=0, rashod_t1=0, rashod_t2=0, t1_current=0,
                                t1_paid=0, service_name='memberfee2021h1', numsite=pinfo.numsite)
    else:
        payd_sum = 2500
        payd_sum_qr_string = 250000
        receipt = ReceiptEntity(name=alias.get('name'), bank_name=alias.get('bank_name'), bic=alias.get('bic'),
                                corresp_acc=alias.get('corresp_acc'), kpp=alias.get('kpp'),
                                payee_inn=alias.get('payee_inn'),
                                personal_acc=alias.get('personal_acc'), first_name=pinfo.first_name,
                                last_name='{} {} {}'.format(pinfo.last_name, pinfo.first_name, pinfo.grand_name),
                                grand_name=pinfo.grand_name,
                                payer_address='{}, {}'.format(pinfo.street_name, pinfo.numsite),
                                purpose='Членский взнос за {} {} Л/C {}, {}'.format(rq.year, '|Phone={}'.format(pinfo.phone), pinfo.street_name, pinfo.numsite),
                                street=pinfo.street_name, counter_type=0, rashod_t1=0, rashod_t2=0, t1_current=0,
                                t1_paid=0, service_name='membership_fee', numsite=pinfo.numsite)

    # qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
    #                     k in response_keys.keys()])

    qr_string = ''
    for k in receipt.dict().keys():
        if k in response_keys.keys():
            if k == 'payer_address':
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))
            else:
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))

    street_id = get_street_id(receipt)

    payer_id = pinfo.payer_id  # '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)
    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}|PersAcc={}'.format(payd_sum_qr_string, rq.year, payer_id)
    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)
    receipt.result_sum = payd_sum
    if rq.year == '2021h1':
        receipt.service_name = 'memberfee2021h1'
    else:
        receipt.service_name = 'membership_fee'

    print(qr_string)
    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    img_url = qr_img.json().get('response').get('url')

    if rq.year == '2021h1':
        resp_sum = 1250
        receipt.purpose = 'Оплата членского взноса 1 полугодие 2021. На выплату задолженности перед АО НЭСК (оферта auditsnt.ru/nesk)'
    else:
        resp_sum = 2500
        receipt.purpose = 'Оплата членского взноса {}. На выплату задолженности перед АО НЭСК (оферта auditsnt.ru/nesk)'.format(
            rq.year)

    delegate_payer_id = None
    if rq.neighbour:
        delegate_personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
        delegate_personal_info: PersonalInfoDB = delegate_personal_infos.items[0]
        delegate_payer_id = delegate_personal_info.payer_id

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=receipt.last_name, delegate_payer_id=delegate_payer_id))

    if rq.neighbour:
        await delegat_action_dao.create(DelegatActionDB(delegated_id=user.id, payer_id=rq.neighbour, receipt_id=id_))

    receipt = await receipt_dao.get(id_)

    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=0, t1_sum=0,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(resp_sum, '00'),
                                 alias_info=AliasInfoResp(**alias))


class AddLossesPrepaidRQ(BaseModel):
    neighbour: Optional[str]


@router.post('/add-losses-prepaid')
async def add_losses_prepaid(rq: AddLossesPrepaidRQ,
                             user: User = Depends(fastapi_users.get_optional_current_active_user)):
    if user == None:
        raise HTTPException(status_code=500, detail='Необходима автаризация')

    alias = get_alias_info('sntzhd')

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    if rq.neighbour:
        personal_infos = await personal_info_dao.list(0, 1, {'payer_id': rq.neighbour})
    else:
        personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
    pinfo: PersonalInfoDB = personal_infos.items[0]

    receipt = ReceiptEntity(name=alias.get('name'), bank_name=alias.get('bank_name'), bic=alias.get('bic'),
                            corresp_acc=alias.get('corresp_acc'), kpp=alias.get('kpp'),
                            payee_inn=alias.get('payee_inn'),
                            personal_acc=alias.get('personal_acc'), first_name=pinfo.first_name,
                            last_name=pinfo.last_name,
                            grand_name=pinfo.grand_name,
                            payer_address='{}, {}'.format(pinfo.street_name, pinfo.numsite),
                            purpose='Потери 15% на 3000 кВт, Л/С {}{}'.format(
                                '{}, {}'.format(pinfo.street_name,
                                                pinfo.numsite),
                                '|Phone={}'.format(pinfo.phone),),
                            street=pinfo.street_name, counter_type=0, rashod_t1=0, rashod_t2=0, t1_current=0,
                            t1_paid=0, service_name='losses.prepaid', numsite=pinfo.numsite)

    # qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
    #                     k in response_keys.keys()])

    qr_string = ''
    for k in receipt.dict().keys():
        if k in response_keys.keys():
            if k == 'payer_address':
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))
            else:
                qr_string += '{}={}|'.format(get_work_key(k), receipt.dict().get(k))

    street_id = get_street_id(receipt)

    payer_id = pinfo.payer_id  # '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)
    qr_string += 'Sum={}|Category=ЖКУ|PersAcc={}'.format(2139, payer_id)
    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)
    receipt.result_sum = 2139
    receipt.service_name = 'losses.prepaid'

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    img_url = qr_img.json().get('response').get('url')

    receipt.purpose = 'Потери 15% Т1 (расход 2000 кВт), Т2 (расход 1000 кВт), согласно Протоколу #9 от 28.03.2015г. На выплату задолженности перед АО НЭСК (оферта auditsnt.ru/nesk)'

    delegate_payer_id = None
    if rq.neighbour:
        delegate_personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
        delegate_personal_info: PersonalInfoDB = delegate_personal_infos.items[0]
        delegate_payer_id = delegate_personal_info.payer_id

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=receipt.last_name, delegate_payer_id=delegate_payer_id))

    if rq.neighbour:
        await delegat_action_dao.create(DelegatActionDB(delegated_id=user.id, payer_id=rq.neighbour, receipt_id=id_))
    receipt = await receipt_dao.get(id_)

    print(receipt)
    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=0, t1_sum=0,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(2139, '00'),
                                 alias_info=AliasInfoResp(**alias))


class ConsumptionResp(BaseModel):
    r1: Optional[Decimal]
    r2: Optional[Decimal]
    ok: bool


def get_receipt_type(value: str) -> ReceiptType:
    membership_fee = False
    electricity = False
    losses = False
    consumption = False
    counter_type = 0

    for v in value:
        if len(re.findall(r'{}'.format('взнос'), v.lower())) > 0:
            membership_fee = True

        if len(re.findall(r'{}'.format('член'), v.lower())) > 0:
            membership_fee = True

        if len(re.findall(r'{}'.format('потери'), v.lower())) > 0:
            losses = True

        if len(re.findall(r'{}'.format('15проц'), v.lower())) > 0:
            losses = True

        if len(re.findall(r'{}'.format('15%'), v.lower())) > 0:
            losses = True

        if len(re.findall(r'{}'.format('Т1'), v)) > 0:
            electricity = True

            if len(re.findall(r'{}'.format('Т2'), v)) > 0:
                counter_type = 2
            else:
                counter_type = 1

        if len(re.findall(r'{}'.format('расход'), v.lower())) > 0:
            consumption = True

    dict_result = dict(membership_fee=membership_fee, electricity=electricity, losses=losses, consumption=consumption)

    if len([dict_result for k in dict_result.keys() if dict_result.get(k)]) == 1:
        return ReceiptType(service_name=[k for k in dict_result.keys() if dict_result.get(k)][0],
                           counter_type=counter_type)


def get_receipt_type_by_1c(value: str) -> ReceiptType:
    membership_fee = False
    electricity = False
    losses = False
    consumption = False
    counter_type = 0

    v = value
    if len(re.findall(r'{}'.format('взнос'), v.lower())) > 0:
        membership_fee = True

    if len(re.findall(r'{}'.format('член'), v.lower())) > 0:
        membership_fee = True

    if len(re.findall(r'{}'.format('потери'), v.lower())) > 0:
        losses = True

    if len(re.findall(r'{}'.format('15проц'), v.lower())) > 0:
        losses = True

    if len(re.findall(r'{}'.format('15%'), v.lower())) > 0:
        losses = True

    if len(re.findall(r'{}'.format('Т1'), v)) > 0:
        electricity = True

        if len(re.findall(r'{}'.format('Т2'), v)) > 0:
            counter_type = 2
        else:
            counter_type = 1

    # if len(re.findall(r'{}'.format('расход'), v.lower())) > 0:
    #    consumption = True

    dict_result = dict(membership_fee=membership_fee, electricity=electricity, losses=losses, consumption=consumption)

    if len([dict_result for k in dict_result.keys() if dict_result.get(k)]) == 1:
        return ReceiptType(service_name=[k for k in dict_result.keys() if dict_result.get(k)][0],
                           counter_type=counter_type)


def get_consumption_with_counter_type(counter_type: int, value: str, current_sum: str,
                                      current_tariff: Dict[str, Any]) -> ConsumptionResp:
    if counter_type == 1:

        electricity_sum = Decimal(current_sum) / Decimal(current_tariff.get('t0_tariff'))
        losses_sum = (Decimal(current_sum) / Decimal(current_tariff.get('t0_tariff'))) * Decimal('0.15')

        electricity_sum_str = str(int(electricity_sum))
        losses_sum_str = str(int(losses_sum))

        if electricity_sum_str in re.findall('\d+', value):
            return ConsumptionResp(r1=Decimal(electricity_sum_str), r2=None, ok=True)

        if losses_sum_str in re.findall('\d+', value):
            return ConsumptionResp(r1=Decimal(losses_sum_str), r2=None, ok=True)

        return ConsumptionResp(r1=None, r2=None, ok=False)
    else:
        r1 = None
        r2 = None
        found = False
        params = value.split(' ')

        for param in params:
            res = re.findall(r'{}'.format('расход'), param.lower())

            if found:
                if r1 == None:
                    r1 = param
                else:
                    r2 = param

            if len(res) > 0:
                found = True
            else:
                found = False

    try:
        r1value = Decimal(r1)
        r2value = Decimal(r2)
        return ConsumptionResp(r1=r1value, r2=r2value, ok=True)
    except TypeError:
        return ConsumptionResp(r1=None, r2=None, ok=False)


def get_counter_type(value: str):
    t1_result = re.findall(r'т1', value.lower())
    t2_result = re.findall(r'т2', value.lower())

    if (len(t1_result) + len(t2_result)) > 0:
        return (len(t1_result) + len(t2_result))
    else:
        return 1


def make_payer_id(value: str, sreets_str: str, alias: Dict[str, Any], dict_streets: Dict[str, Any]):
    params = value.split(' ')
    street_numer = None
    house_number = None

    for param in params:
        sn = dict_streets.get(param.lower())
        if sn:
            street_numer = sn

        if street_numer and house_number == None:
            if len(param) > 0:
                if param[0] == '№':
                    try:
                        house_number = str(int(param[1:]))
                    except ValueError:
                        pass
                else:
                    try:
                        house_number = str(int(param))
                    except ValueError:
                        pass
        else:
            pass

    if street_numer and house_number:
        payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_numer, house_number)
        return payer_id


def old_make_payer_id(value: str, sreets_str: str, alias: Dict[str, Any], dict_streets: Dict[str, Any]):
    if len(re.findall(r';', value)) > 0:
        params = value.split(';')
    else:
        params = value.split(' ')

    for param in params:
        result = re.findall(r'{}'.format(param.split(' ')[0].lower()), sreets_str.lower())
        if len(result) > 0:
            payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8],
                                         dict_streets.get(param.split(' ')[0].lower()), param.split(' ')[1])
            return payer_id
        else:
            street_found = None
            for param in value.split(' '):
                from re import error
                if street_found and len(param) > 0:
                    if param[0] == '№':

                        try:
                            payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8],
                                                         dict_streets.get(street_found), str(int(param[1:])))
                            return payer_id
                        except ValueError:
                            break
                try:
                    result = re.findall(r'{}'.format(param.lower()), sreets_str.lower())
                    if len(result) > 0:
                        street_found = param.lower()

                except error:
                    pass


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


def get_street_by_alias(value: str, alias: Dict[str, Any], dict_streets: Dict[str, Any]):
    pass


def make_payer_id_by_1c(value: str, alias: Dict[str, Any], dict_streets: Dict[str, Any]):
    params = value.split(';')

    street_numer = None
    house_number = None

    for param in params:
        street = get_coincidence_street(param, dict_streets)
        if street:
            street_numer = street.get('street_number')
            house_number = perhaps_house_number(param, street.get('street_name'))
            break

    if street_numer and house_number:
        payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_numer, house_number)
        return payer_id

    get_street_by_alias(value, alias, dict_streets)


@router.post('csv-parser')
async def csv_parser(name_alias: str = 'sntzhd', input_row: str = None, file: UploadFile = File(None)) -> List[
    RawReceiptCheck]:
    async with aiofiles.open('BBBB.csv', 'wb') as out_file:
        content = await file.read()  # async read
        await out_file.write(content)

    f = codecs.open('BBBB.csv', 'r', 'cp1251')
    u = f.read()  # now the contents have been transformed to a Unicode string
    out = codecs.open('ezz.csv', 'wb', 'utf-8')
    out.write(u)

    dict_streets = dict()

    alias = get_alias_info(name_alias)

    r = requests.get(remote_service_config.street_list_url)

    for street in r.json().get('sntList')[0].get('streetList'):
        dict_streets.update({street.get('strName').lower(): street.get('strID')})

    sreets_str = ''.join([street.get('strName') for street in r.json().get('sntList')[0].get('streetList')])

    r = requests.get(remote_service_config.default_data_url)

    current_tariff = r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs')[-1]
    raw_receipt_check_list = []

    read_file_name = 'ezz.csv'

    if input_row:
        with open('testing_data.csv', 'w', newline='') as file:
            writer = csv.writer(file, quoting=csv.QUOTE_ALL)
            writer.writerow([input_row])
            read_file_name = 'testing_data.csv'

    with open(read_file_name, newline='\n') as File:
        reader = csv.reader(File)
        rc = 1
        for row in reader:
            # print('ROW', ' '.join(row))

            payer_id = make_payer_id(' '.join(row), sreets_str, alias, dict_streets)
            value_str = ' '.join(row)
            chack_sum = False
            counter_type = get_counter_type(value_str)

            if payer_id == None:
                continue

            for param in value_str.split(';'):

                if param[:4] == 'СУМ:':

                    if counter_type > 0:
                        consumptions = get_consumption_with_counter_type(counter_type, value_str, param[4:],
                                                                         current_tariff)

                        if consumptions.ok:
                            if counter_type == 1:
                                pay_sum = Decimal(param[4:])
                                t_price = Decimal(current_tariff.get('t0_tariff'))
                                result_sum = consumptions.r1 * t_price
                                if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == pay_sum:
                                    chack_sum = True
                                else:
                                    result_sum = result_sum * Decimal('0.15')
                                    if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == pay_sum:
                                        chack_sum = True
                            else:
                                pay_sum = Decimal(param[4:])
                                t_price = Decimal(current_tariff.get('t1_tariff'))
                                sum1 = consumptions.r1 * t_price
                                sum2 = consumptions.r2 * Decimal(current_tariff.get('t2_tariff'))
                                result_sum = sum1 + sum2

                                if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == pay_sum:
                                    chack_sum = True
                                else:
                                    result_sum = result_sum * Decimal('0.15')
                                    if result_sum.quantize(Decimal("1.00"), ROUND_FLOOR) == pay_sum:
                                        chack_sum = True
                    else:
                        pass

            payment_destination = payment_destination_checker(value_str)
            payment_no_double_destination = payment_no_double_destination_checker(value_str)
            # chack_sum = False

            receipt_type = get_receipt_type(row)

            if payer_id and chack_sum:
                raw_receipt_check_list.append(RawReceiptCheck(title=value_str, test_result=True, payer_id=payer_id,
                                                              needHandApprove=False, receipt_type=receipt_type,
                                                              paid_sum=pay_sum, ))
            else:
                raw_receipt_check_list.append(RawReceiptCheck(title=value_str, test_result=False, payer_id=payer_id,
                                                              needHandApprove=True, paid_sum=pay_sum))

            rc += 1

    return raw_receipt_check_list


class RespChack1c(BaseModel):
    raw_receipt_check_list: List[RawReceiptCheck]
    undefound_clients: List[UndefoundClient]
    all_rows_count: int
    chacking_rows_count: int
    sum_streets: List[StreetSumResp]
    payer_ids_sums: List[PayerIdSum]
    all_sum: Decimal
    sum_streets_result: Decimal
    membership_fee_sum: Decimal
    losses_sum: Decimal
    expense_rows_count: int
    expense_list: List[ExpensePayItem]
    expense_sum: Decimal
    undefound_clients_count: int


def get_street_coordinates(street_list: List[Any], street_name: str):
    for street in street_list:
        if street.get('strName').lower() == street_name:
            return street.get('geometry').get('coordinates')
            print(street.get('geometry').get('coordinates'))
    return []


def get_sum_electricity_payments_by_street(street_electricity_sums_dict: Dict[Any, Any]):
    print(street_electricity_sums_dict, 'get_sum_electricity_payments_by_street')
    return 0


def get_sum_losses_payments_by_street(street_losses_sums_dict: Dict[Any, Any]):
    return 0


def get_sum_memberfee_payments_by_street(dict_street_number_houses: Dict[Any, Any]):
    return 0


def get_sum_to_payer_id(payer_id: str, raw_receipt_check_list: List[RawReceiptCheck]):
    result = 0

    for r in raw_receipt_check_list:
        if r.payer_id == payer_id:
            result += Decimal(r.paid_sum)
    return result


def get_losses_sum_to_payer_id(payer_id: str, raw_receipt_check_list: List[RawReceiptCheck]):
    result = 0

    for r in raw_receipt_check_list:
        if r.receipt_type and r.receipt_type.service_name.value == 'losses':
            if r.payer_id == payer_id:
                result += Decimal(r.paid_sum)
    return result


StreetNames = Enum('StreetNames',
                   [(str(street.get('strID')), street.get('strName').lower()) for street in raw_street_list], start=1)


def get_street_name_by_id(street_id: str) -> str:
    for street in raw_street_list:
        if str(street.get('strID')) == street_id:
            return street.get('strName')
    return 'Другие'


class UserInfo(BaseModel):
    phone: str
    address: str
    neighbors: List[Neighbor] = []


@router.get('/user-info', )
async def user_info(user: User = Depends(fastapi_users.get_current_user)) -> UserInfo:
    personal_infos = await personal_info_dao.list(0, 1, {'user_id': user.id})
    pinfo: PersonalInfoDB = personal_infos.items[0]

    delegats = await delegate_dao.list(0, 1, dict(user_id=user.id))

    neighbors = []

    if delegats.count > 0:
        neighbors = [Neighbor(**(await personal_info_dao.list(0, 100, {'payer_id': payer_id})).items[0].dict()) for
                     payer_id in delegats.items[0].payer_ids]

    return UserInfo(phone=pinfo.phone, address='{} {}'.format(pinfo.street_name, pinfo.numsite), neighbors=neighbors)


class NewNeighborRQ(BaseModel):
    phone: str


@router.post('/add-me-new-neighbor')
async def add_me_new_neighbor(rq: NewNeighborRQ, user: User = Depends(fastapi_users.get_current_user)) -> bool:
    delegats = await delegate_dao.list(0, 1, dict(user_id=user.id))
    print(delegats)

    personal_infos = await personal_info_dao.list(0, 1, {'phone': rq.phone})
    try:
        pinfo: PersonalInfoDB = personal_infos.items[0]
        print(pinfo.payer_id)
    except IndexError:
        raise HTTPException(status_code=404, detail='Не верный номер телефона')

    if delegats.count == 0:
        await delegate_dao.create(DelegateDB(user_id=user.id, payer_ids=[pinfo.payer_id]))
    else:
        delegat: DelegateDB = delegats.items[0]
        if pinfo.payer_id not in delegat.payer_ids:
            delegat.payer_ids.append(pinfo.payer_id)
            await delegate_dao.update(delegat)
    return True


@router.post('parser-1cV2')
async def parser_1c(select_street: StreetNames = None, paymPeriod: str = None, name_alias: str = 'sntzhd',
                    input_row: str = None, file: UploadFile = File(None)) -> RespChack1cV2:
    receipt_check_list: List[RawReceiptCheck] = []
    undefined_client_list: List[UndefinedClient] = []
    street_sums_dict = {'Другие': 0}
    expense_list: List[ExpensePayItem] = []
    expense_rows_count = 0

    async with aiofiles.open('1c_document_utfSAVE.txt', 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    raw_receipts = raw_receipts_creator_by_file()

    all_sum = sum([raw_receipt.amount for raw_receipt in raw_receipts])

    payer_id_checker = PayerIdChecker()

    for raw_receipt in raw_receipts:
        if raw_receipt.payer == 'СНТ "ЖЕЛЕЗНОДОРОЖНИК"':
            expense_rows_count += 1
            expense_list.append(ExpensePayItem(title=raw_receipt.payer, pay_sum=raw_receipt.amount))
            continue

        if raw_receipt.payer.replace('\n',
                                     '') == 'НО Садоводческое некоммерческое товарищество Железнодорожник':
            expense_rows_count += 1
            expense_list.append(ExpensePayItem(title=raw_receipt.payer, pay_sum=raw_receipt.amount))
            continue

        payer_id = payer_id_checker.get_payer_id(raw_receipt.purpose_payment)

        if payer_id_checker.check_payer_id(payer_id):
            result = hashlib.md5(raw_receipt.purpose_payment.encode())
            title_receipt_hash = result.hexdigest()
            receipt_check_list.append(RawReceiptCheck(title=raw_receipt.purpose_payment, test_result=False,
                                                      payer_id=payer_id, needHandApprove=True,
                                                      receipt_type=get_receipt_type_by_1c(raw_receipt.purpose_payment),
                                                      paid_sum=raw_receipt.amount,
                                                      title_receipt_hash=title_receipt_hash,
                                                      receipt_date=raw_receipt.date_received,
                                                      street_name=payer_id_checker.get_street_name_by_id(payer_id)))
            if street_sums_dict.get(payer_id_checker.get_street_name_by_id(payer_id)):
                street_name = payer_id_checker.get_street_name_by_id(payer_id)
                current_sum = street_sums_dict.get(payer_id_checker.get_street_name_by_id(payer_id))
                street_sums_dict.update({street_name: (current_sum + raw_receipt.amount)})
            else:
                street_name = payer_id_checker.get_street_name_by_id(payer_id)
                street_sums_dict.update({street_name: raw_receipt.amount})
        else:
            current_sum = street_sums_dict.get('Другие')
            street_sums_dict.update({'Другие': (current_sum + raw_receipt.amount)})
            undefined_client_list.append(
                UndefinedClient(title=raw_receipt.title_receipt_hash, paid_sum=raw_receipt.amount,
                                payer_id=hashlib.sha256(
                                    raw_receipt.payer.encode(
                                        'utf-8')).hexdigest()))

    houses_on_street = make_houses_on_street(receipt_check_list)
    payments_on_street = make_payments_on_street(receipt_check_list)
    street_losses_sums_dict = make_street_losses_sums_dict(receipt_check_list)
    street_membership_fee_sums_dict = make_street_membership_fee_sums_dict(receipt_check_list)

    all_payer_ids = [r.payer_id for r in receipt_check_list]
    payer_ids_sums = [
        PayerIdSum(payer_id=payer_id, losses_sum=get_losses_sum_to_payer_id(payer_id, receipt_check_list),
                   general_sum=get_sum_to_payer_id(payer_id, receipt_check_list)) for payer_id in
        set(all_payer_ids)]

    street_list = payer_id_checker.get_street_list()

    sum_streets = [StreetSumResp(street_name=k, coordinates=get_street_coordinates(street_list, k),
                                 street_home_qty=len(houses_on_street.get(k)) if houses_on_street.get(k) else 0,
                                 street_payment_qty=payments_on_street.get(k),
                                 electricity_sum=(street_sums_dict.get(k) - (
                                     street_losses_sums_dict.get(k) if street_losses_sums_dict.get(k) else 0) - (
                                                      street_membership_fee_sums_dict.get(
                                                          k) if street_membership_fee_sums_dict.get(k) else 0)),
                                 losses_sum=street_losses_sums_dict.get(k) if street_losses_sums_dict.get(k) else 0,
                                 memberfee_sum=street_membership_fee_sums_dict.get(
                                     k) if street_membership_fee_sums_dict.get(k) else 0,
                                 paymPeriod=paymPeriod,
                                 general_sum=street_sums_dict.get(k)) for k in street_sums_dict.keys()]

    sum_streets_result = sum(sum_street.general_sum for sum_street in sum_streets)

    membership_fee_sum = sum([Decimal(r.paid_sum) for r in receipt_check_list if
                              r.receipt_type and r.receipt_type.service_name.value == 'membership_fee'])
    losses_sum = sum([Decimal(r.paid_sum) for r in receipt_check_list if
                      r.receipt_type and r.receipt_type.service_name.value == 'losses'])

    expense_sum = sum([expense.pay_sum for expense in expense_list])

    return RespChack1cV2(all_rows_count=len(raw_receipts), all_sum=all_sum, undefined_clients=undefined_client_list,
                         undefined_clients_count=len(undefined_client_list), raw_receipt_check_list=receipt_check_list,
                         sum_streets=sum_streets, chacking_rows_count=len(receipt_check_list),
                         payer_ids_sums=payer_ids_sums,
                         sum_streets_result=sum_streets_result, membership_fee_sum=membership_fee_sum,
                         losses_sum=losses_sum, undefound_clients_count=len(undefined_client_list),
                         expense_rows_count=expense_rows_count, expense_list=expense_list, expense_sum=expense_sum)


@router.get('/get-receipts-by-payer-id', )
async def get_receipts_by_payer_id(payer_id: str) -> List[ReceiptDB]:
    return await receipt_dao.list(0, 1000, dict(payer_id=payer_id))
