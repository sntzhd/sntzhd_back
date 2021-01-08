import inject

from backend_api.interfaces import IReceiptDAO, IPersonalInfoDAO
from backend_api.db.receipts.dao import ReceiptDAO, PersonalInfoDAO
from backend_api.db.motor.file import IFileDAO, FileDAO

def base(binder: inject.Binder):
    binder.bind_to_constructor(IReceiptDAO, lambda: ReceiptDAO())
    binder.bind_to_constructor(IPersonalInfoDAO, lambda: PersonalInfoDAO())
    binder.bind_to_constructor(IFileDAO, lambda: FileDAO())
