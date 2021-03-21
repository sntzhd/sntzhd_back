from backend_api.interfaces import IVoteDelegateDAO
from backend_api.db.delegates.models import VoteDelegateDB
from backend_api.db.motor.dao import MotorGenericDAO



class VoteDelegateDAO(MotorGenericDAO, IVoteDelegateDAO):
    def __init__(self):
        super().__init__('delegate_votes', VoteDelegateDB)