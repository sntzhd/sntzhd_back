from backend_api.interfaces import IReceiptDAO, IPersonalInfoDAO
from backend_api.db.receipts.model import ReceiptDB, PersonalInfoDB
from backend_api.db.motor.dao import MotorGenericDAO


class ReceiptDAO(MotorGenericDAO, IReceiptDAO):
    def __init__(self):
        super().__init__('receipts', ReceiptDB)

class PersonalInfoDAO(MotorGenericDAO, IPersonalInfoDAO):
    def __init__(self):
        super().__init__('personal_info', PersonalInfoDB)
