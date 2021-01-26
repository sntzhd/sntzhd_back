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
from typing import Optional, List
from fastapi_users.password import get_password_hash
import calendar
import dateutil.relativedelta
from secrets import choice
import string
import base64
import json
import re

from backend_api.utils import instance
from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO, IDelegateDAO,
                                    IDelegateEventDAO)
from backend_api.entities import ListResponse, ReceiptEntity, PersonalInfoEntity, OldReceiptEntity
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

url_streets = 'https://next.json-generator.com/api/json/get/N1kZKVgpK'

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

sntzhd = dict(name='СНТ \\"ЖЕЛЕЗНОДОРОЖНИК\\"', bank_name='Филиал \\"Центральный\\" Банка ВТБ (ПАО) в г. Москве',
              bic='044525411', corresp_acc='30101810145250000411', kpp='231201001', payee_inn='2312088371',
              personal_acc='40703810007550006617', purpose='Оплата электроэнергии по договору №10177', id='0883')

aliases = dict(sntzhd=sntzhd)


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
lose_text = 'ПОТЕРИ 15% СОГЛАСНОПРОТОКОЛУ №9 ОТ 28.03.2015Г'


@router.post('/create-receipt', description='Создание квитанции')
async def create_receipt(receipt: ReceiptEntity) -> CreateReceiptResponse:
    current_tariff = None

    alias = aliases.get(receipt.alias)

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    street_id = None

    r_streets = requests.get(url_streets)

    for snt in r_streets.json()['sntList']:
        if snt.get('alias') == receipt.alias:
            for street in snt.get('streetList'):
                if street.get('strName') == receipt.street:
                    street_id = street.get('strID')

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, receipt.numsite)

    print(payer_id, 'payer_idpayer_idpayer_id')

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
    print(remote_service_config.default_data_url)

    for tariff in r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs'):

        if current_tariff:
            if int(str(tariff.get('paymPeriod'))[-4:]) >= int(str(current_tariff.get('paymPeriod'))[-4:]) and int(
                    str(tariff.get('paymPeriod'))[:-4]) > int(str(current_tariff.get('paymPeriod'))[:-4]):
                current_tariff = tariff
        else:
            current_tariff = tariff

    current_tariff = r.json().get('Kontragents')[0].get('2312088371').get('services')[0].get('tariffs')[-1]

    receipts = await receipt_dao.list(0, HISTORY_PAGE_SIZE, {'payer_address': receipt.payer_address})

    if receipts.count > 0:
        if receipt.t1_current <= receipts.items[0].t1_current:
            raise HTTPException(status_code=500,
                                detail='Ошибка # Не верное значение. Значение прошлого периода {} кВт'.format(
                                    receipts.items[0].rashod_t1))
        t1_sum = receipt.rashod_t1 * float(current_tariff.get('t0_tariff')) if receipt.counter_type == 1 else float(
            current_tariff.get('t1_tariff'))

        print(t1_sum, 't0_tarifft0_tarifft0_tariff')
        t2_sum = receipt.rashod_t2 * float(current_tariff.get('t2_tariff'))
        result_sum = t1_sum + t2_sum
    else:
        t1_sum = receipt.rashod_t1 * float(current_tariff.get('t0_tariff')) if receipt.counter_type == 1 else float(
            current_tariff.get('t1_tariff'))
        t2_sum = receipt.rashod_t2 * float(current_tariff.get('t2_tariff'))
        result_sum = t1_sum + t2_sum

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
        receipt.purpose = 'Т {} (расход {} кВт), {}, {} {}'.format(receipt.t1_current, receipt.rashod_t1,
                                                                   receipt.payer_address, receipt.purpose,
                                                                   el_text if receipt.service_name == 'electricity' else lose_text)

    qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
                         k in response_keys.keys()])

    dt = datetime.datetime.now()

    paym_period = '{}{}'.format(dt.month, dt.year) if dt.day <= 10 else '{}{}'.format((dt.month - 1), dt.year)

    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}'.format(int((result_sum * 100)), paym_period)
    # payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    print(qr_img.json().get('response'))

    img_url = qr_img.json().get('response').get('url')

    t1_expense = receipt.t1_current * receipt.t1_paid
    t1_sum = float(current_tariff.get('t0_tariff'))

    print(receipt.purpose, 'dddddddddddddddddd')

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique'),
                                             last_name_only=last_name_only))
    receipt = await receipt_dao.get(id_)

    try:
        sum_rub, sum_cop = str(receipt.result_sum).split('.')
    except ValueError:
        sum_rub = str(receipt.result_sum)
        sum_cop = '00'

    print(receipt.purpose, 'DBDBDBD')
    return CreateReceiptResponse(img_url=img_url, receipt=receipt, t1_expense=t1_expense, t1_sum=t1_sum,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(sum_rub, sum_cop),
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

    print(filters, 'filtersfiltersfilters')

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

    print(r)

    t = templates.TemplateResponse("receipt_new.html",
                                   {"request": request, 'year': r.created_date.year,
                                    'month': months.get(r.created_date.month),
                                    'day': r.created_date.day, 'sum_rub': sum_rub, 'sum_cop': sum_cop,
                                    'Sum': r.result_sum, 'Name': sntzhd.get('name'),
                                    'KPP': sntzhd.get('kpp'), 'PayeeINN': sntzhd.get('payee_inn'),
                                    'PersonalAcc': sntzhd.get('personal_acc'), 'BankName': sntzhd.get('bank_name'),
                                    'BIC': sntzhd.get('bic'),
                                    'CorrespAcc': sntzhd.get('corresp_acc'), 'КБК': '1', 'purpose': r.purpose,
                                    'payerAddress': r.payer_address, 'lastName': r.last_name, 'img_url': r.img_url}
                                   )
    print(dir(r.result_sum))
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
        print(personal_infos)
        print(user.id, 'fffffffffff')
        print(receipts.items[0].payer_id)

    receipts = await receipt_dao.list(0, 1, {'payer_address': payer_address})
    print(receipts.items[0].payer_id)
    return OldValueResp(item=receipts.items[0], count=receipts.count, access_upload=access_upload)


@router.post('/save-pi', description='Сохранение данных платильщика')
async def save_pi(personal_info: PersonalInfoEntity) -> str:
    personal_infos = await personal_info_dao.list(0, 1, {'phone': personal_info.phone})

    alias = aliases.get(personal_info.snt_alias)

    if alias == None:
        raise HTTPException(status_code=500, detail='Не верный alias')

    street_id = None

    r_streets = requests.get(url_streets)

    for snt in r_streets.json()['sntList']:
        if snt.get('alias') == personal_info.snt_alias:
            for street in snt.get('streetList'):
                if street.get('strName') == personal_info.street_name:
                    street_id = street.get('strID')

    payer_id = '{}-{}-{}'.format(alias.get('payee_inn')[4:8], street_id, personal_info.numsite)
    personal_info.payer_id = payer_id
    print(personal_infos)
    if personal_infos.count == 0:
        phone = personal_info.phone
        if personal_info.phone[0] == '+':
            phone = personal_info.phone[1:]

        print(phone, 'phone')

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
                                 formating_sum='{} руб {} коп'.format(sum_rub, sum_cop))


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
    print(user_in_db)

    if user_in_db == None:
        if rq.phone[0] == '+':
            user_in_db = await user_db.get_by_email('{}@online.pay'.format(rq.phone[1:]))
        else:
            user_in_db = await user_db.get_by_email('+{}@online.pay'.format(rq.phone))

    print(user_in_db, 'user_in_db')

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
        print(code)
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
            print(delegate_events.items[0].delegated_id)
            print(delegate.client_ids)
            if delegate_events.items[0].delegated_id not in delegate.client_ids:
                delegate.client_ids.append(delegate_events.items[0].delegated_id)
                await delegate_dao.update(delegate)


@router.get('/delegates')
async def delegates(user=Depends(fastapi_users.get_current_user)) -> List[PayerInfo]:
    delegates = await delegate_dao.list(0, 1, dict(user_id=user.id))
    print(delegates)

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


class RawReceiptCheck(BaseModel):
    title: str
    test_result: bool


@router.post('csv-parser')
async def csv_parser() -> List[RawReceiptCheck]:
    import codecs

    # f = codecs.open('/home/tram/PycharmProjects/base_register_back/Statement_20210101-example.csv', 'r', 'cp1251')
    # u = f.read()  # now the contents have been transformed to a Unicode string
    # out = codecs.open('e.csv', 'w', 'utf-8')
    # out.write(u)

    raw_receipt_check_list = []

    import csv

    with open('/home/tram/PycharmProjects/base_register_back/e.csv', newline='\n') as File:
        reader = csv.reader(File)
        rc = 1
        for row in reader:
            payment_no_double_destination = False

            value_str = ' '.join(row)

            print(value_str)
            payment_destination = payment_destination_checker(value_str)
            payment_no_double_destination = payment_no_double_destination_checker(value_str)

            if payment_destination and payment_no_double_destination:
                raw_receipt_check_list.append(RawReceiptCheck(title=value_str, test_result=True))
            else:
                raw_receipt_check_list.append(RawReceiptCheck(title=value_str, test_result=False))

            print('######################################################{}'.format(rc))
            rc += 1

    return raw_receipt_check_list
