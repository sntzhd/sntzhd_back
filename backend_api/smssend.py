import requests

from config import secret_config

SMS_SERVICE_URL = 'https://sms.ru/sms/send'


def send_sms(phone_number: str, msg: str):
	from backend_api.smsc_api import SMSC
	smsc = SMSC()
	r = smsc.send_sms(phone_number, msg, sender="sms")
	print(r)
	#r = requests.get(SMS_SERVICE_URL, params=dict(api_id=secret_config.SMS_SERVIE_ID, to=phone_number, msg=msg, json=1))
	#print(r.text)
	#return r.json().get('status')
