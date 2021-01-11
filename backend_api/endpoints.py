from fastapi import APIRouter, File, UploadFile, HTTPException, Request
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

from backend_api.utils import instance
from backend_api.interfaces import IReceiptDAO, IPersonalInfoDAO
from backend_api.entities import ListResponse, ReceiptEntity, PersonalInfoEntity
from backend_api.db.receipts.model import ReceiptDB, PersonalInfoDB
from config import remote_service_config
from backend_api.db.motor.file import IFileDAO
from backend_api.db.exceptions import NotFoundError

router = APIRouter()

HISTORY_PAGE_SIZE = 20

receipt_dao: IReceiptDAO = instance(IReceiptDAO)
personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)
file_dao = instance(IFileDAO)

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

sntzhd = dict(name = 'СНТ \\"ЖЕЛЕЗНОДОРОЖНИК\\"', bank_name = 'Филиал \\"Центральный\\" Банка ВТБ (ПАО) в г. Москве',
              bic = '044525411', corresp_acc = '30101810145250000411', kpp = '231201001', payee_inn = '2312088371',
              personal_acc = '40703810007550006617', purpose='Оплата электроэнергии по договору №10177', id='0883')

aliases = dict(sntzhd=sntzhd)


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


@router.post('/create-receipt', description='Создание квитанции')
async def create_receipt(receipt: ReceiptEntity) -> CreateReceiptResponse:
    current_tariff = None

    alias = aliases.get(receipt.alias)

    if alias == None:
        raise HTTPException(status_code=500,detail='Не верный alias')

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

    #receipt.name = 'СНТ \\"ЖЕЛЕЗНОДОРОЖНИК\\"'
    #receipt.bank_name = 'Филиал \\"Центральный\\" Банка ВТБ (ПАО) в г. Москве'
    #receipt.bic = '044525411'
    #receipt.corresp_acc = '30101810145250000411'
    #receipt.kpp = '231201001'
    #receipt.payee_inn = '2312088371'
    #receipt.personal_acc = '40703810007550006617'

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
    receipt.last_name = '{} {}. {}.'.format(receipt.last_name, receipt.first_name[0], receipt.grand_name[0])

    receipt.purpose = 'Т {} (расход {} кВт), {}, {}'.format(receipt.t1_current, receipt.rashod_t1,
                                                            receipt.payer_address, receipt.purpose)

    qr_string = ''.join(['{}={}|'.format(get_work_key(k), receipt.dict().get(k)) for k in receipt.dict().keys() if
                         k in response_keys.keys()])

    dt = datetime.datetime.now()

    paym_period = '{}{}'.format(dt.month, dt.year) if dt.day <= 10 else '{}{}'.format((dt.month - 1), dt.year)

    qr_string += 'Sum={}|Category=ЖКУ|paymPeriod={}'.format(int((result_sum * 100)), paym_period)
    #payer_id = '{}{}{}'.format(receipt.payee_inn[5:8], 'strID', receipt.numsite)

    qr_img = requests.post('https://functions.yandexcloud.net/d4edmtn5porf8th89vro',
                           json={"function": "getQRcode",
                                 "request": {
                                     "string": 'ST00012|{}'.format(qr_string)
                                 }})

    print(qr_img.json().get('response'))

    img_url = qr_img.json().get('response').get('url')

    id_ = await receipt_dao.create(ReceiptDB(**receipt.dict(), qr_string=qr_string, payer_id=payer_id, img_url=img_url,
                                             bill_qr_index=qr_img.json().get('response').get('unique')))
    receipt = await receipt_dao.get(id_)

    try:
        sum_rub, sum_cop = str(receipt.result_sum).split('.')
    except ValueError:
        sum_rub = str(receipt.result_sum)
        sum_cop = '00'

    return CreateReceiptResponse(img_url=img_url, receipt=receipt,
                                 formating_date='{} {} {}'.format(receipt.created_date.day,
                                                                  months.get(receipt.created_date.month),
                                                                  receipt.created_date.year),
                                 formating_sum='{} руб {} коп'.format(sum_rub, sum_cop))


@router.get('/receipts')
async def receipts(page: int = 0, street: str = None, start: str = None, end: str = None):
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


@router.delete('/delete-receipt')
async def delete_receipt(record_id: UUID4):
    # r = await receipt_dao.get(record_id)
    await receipt_dao.delete(record_id)
    # print(r)


@router.get('/get-pdf')
async def get_pdf(request: Request, order_id: UUID4):
    templates = Jinja2Templates(directory="templates")

    r: ReceiptDB = await receipt_dao.get(order_id)

    try:
        sum_rub, sum_cop = str(r.result_sum).split('.')
    except ValueError:
        sum_rub = str(r.result_sum)
        sum_cop = '00'

    t = templates.TemplateResponse("receipt_new.html",
                                   {"request": request, 'year': r.created_date.year,
                                    'month': months.get(r.created_date.month),
                                    'day': r.created_date.day, 'sum_rub': sum_rub, 'sum_cop': sum_cop,
                                    'Sum': r.result_sum, 'Name': r.name, 'KPP': r.kpp, 'PayeeINN': r.payee_inn,
                                    'PersonalAcc': r.personal_acc, 'BankName': r.bank_name, 'BIC': r.bic,
                                    'CorrespAcc': r.corresp_acc, 'КБК': '1', 'purpose': r.purpose,
                                    'payerAddress': r.payer_address, 'lastName': r.last_name, 'img_url': r.img_url}
                                   )
    print(dir(r.result_sum))
    pdf = weasyprint.HTML(string=str(t.body, 'utf-8')).write_pdf()
    open('order.pdf', 'wb').write(pdf)

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return FileResponse('{}/order.pdf'.format(BASE_DIR))


@router.get('/get-old-value')
async def get_old_value(payer_address: str):
    receipts = await receipt_dao.list(0, 1, {'payer_address': payer_address})
    return ListResponse(items=receipts.items, count=receipts.count)


@router.post('/save-pi', description='Сохранение данных платильщика')
async def save_pi(personal_info: PersonalInfoEntity) -> str:
    personal_infos = await personal_info_dao.list(0, 1, {'phone': personal_info.phone})

    if personal_infos.count == 0:
        await personal_info_dao.create(PersonalInfoDB(**personal_info.dict()))


@router.get('/get-receipt')
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
    file_dao = instance(IFileDAO)

    id_ = await file_dao.add(file)

    return id_


@router.get('/change-status')
async def change_status(receipt_id: UUID4):
    receipt: ReceiptDB = await receipt_dao.get(receipt_id)
    receipt.status = 'paid'
    await receipt_dao.update(receipt)
