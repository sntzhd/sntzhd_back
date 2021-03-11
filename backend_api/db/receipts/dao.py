from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IDelegateDAO, IDelegateEventDAO, ICheckingNumberDAO,
                                    IDelegatActionDAO)
from backend_api.db.receipts.model import (ReceiptDB, PersonalInfoDB, DelegateDB, DelegateEventDB, CheckingNumberDB,
                                           DelegatActionDB)
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

class CheckingNumberDAO(MotorGenericDAO, ICheckingNumberDAO):
    def __init__(self):
        super().__init__('checking_numbers', CheckingNumberDB)

class DelegatActionDAO(MotorGenericDAO, IDelegatActionDAO):
    def __init__(self):
        super().__init__('delegat_actions', DelegatActionDB)

