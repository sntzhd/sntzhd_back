from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel
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

from backend_api.utils import instance, get_alias_info, get_street_id, get_streets
from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO, IDelegateDAO,
                                    IDelegateEventDAO)
from backend_api.entities import ListResponse, ReceiptEntity, PersonalInfoEntity, OldReceiptEntity, ReceiptType
from backend_api.db.receipts.model import ReceiptDB, PersonalInfoDB, DelegateEventDB, DelegateDB
from backend_api.db.bonuses.models import BonusAccDB, BonusHistoryDB
from config import remote_service_config
from backend_api.db.motor.file import IFileDAO
from backend_api.db.exceptions import NotFoundError
from backend_api.services.auth_service.endpoints import user_db, UserDB
from backend_api.utils import create_id
from backend_api.smssend import send_sms
from backend_api.services.auth_service.endpoints import fastapi_users
from config import secret_config
from backend_api.parser_utils import check_sum, get_addresses_by_hash
from backend_api.static_data import street_aliases

router = APIRouter()

HISTORY_PAGE_SIZE = 20

receipt_dao: IReceiptDAO = instance(IReceiptDAO)
personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)
file_dao = instance(IFileDAO)
bonus_acc_dao = instance(IBonusAccDAO)
bonus_history_dao = instance(IBonusHistoryDAO)
delegate_dao = instance(IDelegateDAO)
delegate_event_dao = instance(IDelegateEventDAO)

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


@router.post('/create-receipt', description='Создание квитанции')
async def create_receipt(receipt: ReceiptEntity) -> CreateReceiptResponse:
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

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)

    receipt.name = alias.get('name')
    receipt.bank_name = alias.get('bank_name')
    receipt.bic = alias.get('bic')
    receipt.corresp_acc = alias.get('corresp_acc')
    receipt.kpp = alias.get('kpp')
    receipt.payee_inn = alias.get('payee_inn')
    receipt.personal_acc = alias.get('personal_acc')

    # receipt.name = 'СНТ \\"ЖЕЛЕЗНОДОРОЖНИК\\"'
    # receipt.bank_name = 'Филиал \\"Центральный\\" Банка ВТБ (ПАО) в г. Москве'
    # receipt.bic = '044525411'
    # receipt.corresp_acc = '30101810145250000411'
    # receipt.kpp = '231201001'
    # receipt.payee_inn = '2312088371'
    # receipt.personal_acc = '40703810007550006617'

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
            #raise HTTPException(status_code=500,
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
    receipt.last_name = '{} {}. {}.'.format(receipt.last_name, receipt.first_name[0], receipt.grand_name[0])

    if receipt.counter_type == 2:
        receipt.purpose = 'Т1 {} (расход {} кВт),'.format(receipt.t1_current, receipt.rashod_t1)

        t2p = 'Т2 {} (расход {} кВт)'.format(receipt.t2_current, receipt.rashod_t2,
                                             )
        receipt.purpose = '{}\n{}, {}, {}'.format(receipt.purpose, t2p, receipt.payer_address,
                                                  el_text if receipt.service_name == 'electricity' else lose_text)
    else:
        receipt.purpose = 'Т {} (расход {} кВт), {}, {}'.format(receipt.t1_current, receipt.rashod_t1,
                                                                receipt.payer_address,
                                                                el_text if receipt.service_name == 'electricity' else lose_text)

    qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
                         k in response_keys.keys()])



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

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=last_name_only))
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

    t = templates.TemplateResponse("receipt_new.html",
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


class User(BaseModel):
    id: UUID4
    username: str
    email: str
    is_active: bool
    is_superuser: bool


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
        if personal_info.phone[0] == '+':
            phone = personal_info.phone[1:]

        user_in_db = await user_db.create(UserDB(id=create_id(), hashed_password=get_password_hash('1111'),
                                                 email='{}@online.pay'.format(phone), name='',
                                                 lastname='', grandname='', city='', street='', home='',
                                                 phone=personal_info.phone, payer_id=payer_id))

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

    try:
        sum_rub, sum_cop = str(receipt.result_sum).split('.')
    except ValueError:
        sum_rub = str(receipt.result_sum)
        sum_cop = '00'

    return CreateReceiptResponse(img_url=receipt.img_url, receipt=receipt,
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
    user_in_db = await user_db.get_by_email('{}@online.pay'.format(rq.phone))

    if user_in_db == None:
        if rq.phone[0] == '+':
            user_in_db = await user_db.get_by_email('{}@online.pay'.format(rq.phone[1:]))
        else:
            user_in_db = await user_db.get_by_email('+{}@online.pay'.format(rq.phone))

    if user_in_db:
        password = ''.join([choice(string.digits) for _ in range(6)])
        user_in_db.hashed_password = get_password_hash(password)
        await user_db.update(user_in_db)

        if secret_config.SEND_SMS:
            send_sms_status = send_sms(rq.phone, password)

            if send_sms_status == False:
                raise HTTPException(status_code=500, detail='Ошибка сервиса')
        else:
            print(password)

        return password
    else:
        raise HTTPException(status_code=500, detail='Нет в базе')


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


class MembershipReceiptEntity(ReceiptEntity):
    year: str


@router.post('/add-membership-fee')
async def add_membership_fee(receipt: MembershipReceiptEntity):
    alias = get_alias_info(receipt.alias)

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
                         k in response_keys.keys()])

    street_id = get_street_id(receipt)

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)
    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}|PersAcc={}'.format(2500, receipt.year, payer_id)
    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)
    receipt.result_sum = 2500
    receipt.service_name = 'membership_fee'

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    img_url = qr_img.json().get('response').get('url')

    receipt.purpose = 'Оплата членского взноса {}. На выплату задолженности перед АО НЭСК (оферта auditsnt.ru/nesk)'.format(
        receipt.year)

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=receipt.last_name))

    receipt = await receipt_dao.get(id_)

    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=0, t1_sum=0,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(2500, '00'),
                                 alias_info=AliasInfoResp(**alias))





class RawReceiptCheck(BaseModel):
    title: str
    test_result: bool
    payer_id: Optional[str]
    needHandApprove: bool
    receipt_type: Optional[ReceiptType]
    paid_sum: str


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

    #if len(re.findall(r'{}'.format('расход'), v.lower())) > 0:
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

def get_coincidence_street(param: str, dict_streets: Dict[str, Any]):
    for k in dict_streets.keys():
        if len(re.findall(r'{}'.format(k), param.lower())) > 0:
            return dict(street_name=k, street_number=dict_streets.get(k))

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
                        v = [l[(len(l)-1)]]
                        return str(int(v[0]))
                    except ValueError:
                        pass


    #print('comma_params NO', space_params)

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
async def csv_parser(name_alias: str = 'sntzhd', input_row: str = None, file: UploadFile = File(None)) -> List[RawReceiptCheck]:


    async with aiofiles.open('BBBB.csv', 'wb') as out_file:
        content = await file.read()  # async read
        await out_file.write(content)

    import codecs

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
                                                              needHandApprove=False, receipt_type=receipt_type, paid_sum=pay_sum))
            else:
                raw_receipt_check_list.append(RawReceiptCheck(title=value_str, test_result=False, payer_id=payer_id,
                                                              needHandApprove=True, receipt_type=receipt_type, paid_sum=pay_sum))

            rc += 1

    return raw_receipt_check_list


class StreetSumResp(BaseModel):
    street_name: str
    street_sum: Decimal

class UndefoundClient(BaseModel):
    title: str
    payer_id: str
    paid_sum: str

class RespChack1c(BaseModel):
    raw_receipt_check_list: List[RawReceiptCheck]
    undefound_clients: List[UndefoundClient]
    all_rows_count: int
    chacking_rows_count: int
    sum_streets: List[StreetSumResp]
    all_sum: Decimal



@router.post('parser-1c')
async def parser_1c(name_alias: str = 'sntzhd', input_row: str = None, file: UploadFile = File(None)) -> RespChack1c:
    dict_streets = dict()
    key_id_dict_streets = dict()
    paid_sum = None
    raw_receipt_check_list = []
    undefound_clients: List[UndefoundClient] = []
    all_rows_count = 0
    chacking_rows_count = 0
    all_sum = 0
    street_sums_dict = {'Другие': 0}

    hash_addresses = get_addresses_by_hash()

    async with aiofiles.open('1c_document_utfSAVE.txt', 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)


    r = requests.get(remote_service_config.default_data_url)
    current_tariff = r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs')[-1]

    alias = get_alias_info(name_alias)

    r = requests.get(remote_service_config.street_list_url)

    for street in r.json().get('sntList')[0].get('streetList'):
        if street.get('strName'):
            key_id_dict_streets.update({street.get('strID'): street.get('strName').lower()})
            dict_streets.update({street.get('strName').lower(): street.get('strID')})

    f = open('1c_document_utfSAVE.txt')

    doc_dict = dict()
    is_doc = False


    current_paeer_text = None

    for line in f:
        result = re.findall(r'СекцияДокумент', line)

        if len(result) > 0:
            is_doc = True

        result = re.findall(r'КонецДокумента', line)

        if len(result) > 0:
            is_doc = False


        if is_doc:
            if line[:11] == 'Плательщик1':
                current_paeer_text = line[12:]
                if len(re.findall(r'СНТ', current_paeer_text)) > 0:
                    continue

            if line[:5] == 'Сумма':
                paid_sum = Decimal(line[6:])
                all_sum += paid_sum

            if line[:17] == 'НазначениеПлатежа':
                payer_id = make_payer_id_by_1c(line, alias, dict_streets)

                all_rows_count += 1

                if payer_id == None:
                    for hash_address in hash_addresses:
                        if hash_address.get('payer_id') == hashlib.sha256(current_paeer_text.encode('utf-8')).hexdigest():
                            try:
                                street_name, house_number = hash_address.get('payer_adress').split(',')

                                payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], dict_streets.get(street_name.lower()), house_number.replace(' ', ''))

                            except ValueError:
                                undefound_clients.append(UndefoundClient(title=line, paid_sum=paid_sum,
                                                                         payer_id=hashlib.sha256(
                                                                             current_paeer_text.encode(
                                                                                 'utf-8')).hexdigest()))
                                street_sums_dict['Другие'] += Decimal(paid_sum)
                            continue
                    if payer_id == None:
                        continue


                chacking_rows_count += 1

                receipt_type = get_receipt_type_by_1c(line)

                if receipt_type:
                    check_sum_status = check_sum(paid_sum, line, receipt_type, current_tariff)

                    if check_sum_status:
                        raw_receipt_check_list.append(
                            RawReceiptCheck(title=line, test_result=True, payer_id=payer_id,
                                            needHandApprove=False, receipt_type=receipt_type, paid_sum=paid_sum))
                    else:
                        raw_receipt_check_list.append(
                            RawReceiptCheck(title=line, test_result=False, payer_id=payer_id,
                                            needHandApprove=True, receipt_type=receipt_type, paid_sum=paid_sum))




    for raw_receipt_check in raw_receipt_check_list:
        street_name = key_id_dict_streets.get(int(raw_receipt_check.payer_id[5:9]))
        if street_sums_dict.get(street_name):
            street_sum_value = street_sums_dict.get(street_name)
            street_sums_dict.update({street_name: (street_sum_value + Decimal(raw_receipt_check.paid_sum))})
        else:
            street_sums_dict.update({street_name: Decimal(raw_receipt_check.paid_sum)})




    sum_streets = [StreetSumResp(street_name=k, street_sum=street_sums_dict.get(k)) for k in street_sums_dict.keys()]


    for uc in undefound_clients:
        raw_receipt_check_list.append(RawReceiptCheck(title=uc.title, test_result=False, payer_id=uc.payer_id,
                        needHandApprove=True, receipt_type=receipt_type, paid_sum=uc.paid_sum))


    return RespChack1c(raw_receipt_check_list=raw_receipt_check_list, undefound_clients=undefound_clients, all_sum=all_sum,
                       all_rows_count=all_rows_count, chacking_rows_count=chacking_rows_count, sum_streets=sum_streets)
