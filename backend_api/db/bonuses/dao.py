from backend_api.interfaces import IBonusAccDAO, IBonusHistoryDAO
from backend_api.db.bonuses.models import BonusAccDB, BonusHistoryDB
from backend_api.db.motor.dao import MotorGenericDAO


class BonusAccDAO(MotorGenericDAO, IBonusAccDAO):
    def __init__(self):
        super().__init__('bonus_accs', BonusAccDB)


class BonusHistoryDAO(MotorGenericDAO, IBonusHistoryDAO):
    def __init__(self):
        super().__init__('bonusHistory', BonusHistoryDB)
