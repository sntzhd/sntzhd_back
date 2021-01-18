import inject

from backend_api.interfaces import IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO
from backend_api.db.receipts.dao import ReceiptDAO, PersonalInfoDAO
from backend_api.db.motor.file import IFileDAO, FileDAO
from backend_api.db.bonuses.dao import BonusHistoryDAO, BonusAccDAO

def base(binder: inject.Binder):
    binder.bind_to_constructor(IReceiptDAO, lambda: ReceiptDAO())
    binder.bind_to_constructor(IPersonalInfoDAO, lambda: PersonalInfoDAO())
    binder.bind_to_constructor(IFileDAO, lambda: FileDAO())
    binder.bind_to_constructor(IBonusAccDAO, lambda: BonusAccDAO())
    binder.bind_to_constructor(IBonusHistoryDAO, lambda: BonusHistoryDAO())
