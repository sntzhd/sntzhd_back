import random

from backend_api.utils import greensmsru_send_sms, smsru_send_sms, smsc_send_sms



def send_sms(phone_number: str, msg: str):

	sms_sernders = [greensmsru_send_sms, smsru_send_sms, smsc_send_sms]

	random.shuffle(sms_sernders)

	for sms_sernder in sms_sernders:
		result = sms_sernder(phone_number, msg)
		if result:
			return True

	return False
