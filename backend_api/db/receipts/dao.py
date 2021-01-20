from backend_api.interfaces import IReceiptDAO, IPersonalInfoDAO, IDelegateDAO, IDelegateEventDAO
from backend_api.db.receipts.model import ReceiptDB, PersonalInfoDB, DelegateDB, DelegateEventDB
from backend_api.db.motor.dao import MotorGenericDAO


class ReceiptDAO(MotorGenericDAO, IReceiptDAO):
    def __init__(self):
        super().__init__('receipts', ReceiptDB)


class PersonalInfoDAO(MotorGenericDAO, IPersonalInfoDAO):
    def __init__(self):
        super().__init__('personal_info', PersonalInfoDB)


class DelegateDAO(MotorGenericDAO, IDelegateDAO):
    def __init__(self):
        super().__init__('delegates', DelegateDB)


class DelegateEventDAO(MotorGenericDAO, IDelegateEventDAO):
    def __init__(self):
        super().__init__('delegate_events', DelegateEventDB)
