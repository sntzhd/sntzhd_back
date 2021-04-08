import inject

from backend_api.interfaces import (IReceiptDAO, IPersonalInfoDAO, IBonusAccDAO, IBonusHistoryDAO, IDelegateDAO,
                                    IDelegateEventDAO, ICheckingNumberDAO, IProblemDAO, IVoteDAO, IDelegatActionDAO,
                                    IVoteDelegateDAO, IRDataDAO)
from backend_api.db.receipts.dao import (ReceiptDAO, PersonalInfoDAO, DelegateDAO, DelegateEventDAO, CheckingNumberDAO,
                                         DelegatActionDAO, RDataDAO)
from backend_api.db.motor.file import IFileDAO, FileDAO
from backend_api.db.bonuses.dao import BonusHistoryDAO, BonusAccDAO
from backend_api.db.problems.dao import ProblemDAO, VoteDAO
from backend_api.db.delegates.dao import VoteDelegateDAO

def base(binder: inject.Binder):
    binder.bind_to_constructor(IReceiptDAO, lambda: ReceiptDAO())
    binder.bind_to_constructor(IPersonalInfoDAO, lambda: PersonalInfoDAO())
    binder.bind_to_constructor(IFileDAO, lambda: FileDAO())
    binder.bind_to_constructor(IBonusAccDAO, lambda: BonusAccDAO())
    binder.bind_to_constructor(IBonusHistoryDAO, lambda: BonusHistoryDAO())
    binder.bind_to_constructor(IDelegateDAO, lambda: DelegateDAO())
    binder.bind_to_constructor(IDelegateEventDAO, lambda: DelegateEventDAO())
    binder.bind_to_constructor(ICheckingNumberDAO, lambda: CheckingNumberDAO())
    binder.bind_to_constructor(IProblemDAO, lambda: ProblemDAO())
    binder.bind_to_constructor(IVoteDAO, lambda: VoteDAO())
    binder.bind_to_constructor(IDelegatActionDAO, lambda: DelegatActionDAO())
    binder.bind_to_constructor(IVoteDelegateDAO, lambda: VoteDelegateDAO())
    binder.bind_to_constructor(IRDataDAO, lambda: RDataDAO())
