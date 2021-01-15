import requests

from config import secret_config

SMS_SERVICE_URL = 'https://sms.ru/sms/send'


def send_sms(phone_number: str, msg: str):
	r = requests.get(SMS_SERVICE_URL, params=dict(api_id=secret_config.SMS_SERVIE_ID, to=phone_number, msg=msg, json=1))
	print(r.text)
	return r.json().get('status')
