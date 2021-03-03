from backend_api.interfaces import IProblemDAO, IVoteDAO
from backend_api.db.problems.models import ProblemDB, VoteDB
from backend_api.db.motor.dao import MotorGenericDAO


class ProblemDAO(MotorGenericDAO, IProblemDAO):
    def __init__(self):
        super().__init__('problems', ProblemDB)

class VoteDAO(MotorGenericDAO, IVoteDAO):
    def __init__(self):
        super().__init__('votes', VoteDB)
