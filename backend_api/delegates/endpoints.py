from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel, Field
from typing import List, Any

from backend_api.interfaces import IVoteDelegateDAO, IDelegateDAO, IPersonalInfoDAO
from backend_api.db.delegates.models import VoteDelegateDB, VoteDelegateValues
from backend_api.services.auth_service.endpoints import fastapi_users
from backend_api.utils import instance
from backend_api.entities import ListResponse
from config import remote_service_config

HISTORY_PAGE_SIZE = 20

delegate_vote_dao: IVoteDelegateDAO = instance(IVoteDelegateDAO)
delegate_dao: IDelegateDAO = instance(IDelegateDAO)
personal_info_dao: IPersonalInfoDAO = instance(IPersonalInfoDAO)

router = APIRouter()


class VoteDelegateRq(BaseModel):
    delegate_id: UUID4
    vote_value: VoteDelegateValues


@router.post('/vote', description='Проголосовать за делегата')
async def report_problem(rq: VoteDelegateRq, user=Depends(fastapi_users.get_current_user)):
    filters = dict(user_id=user.id, delegate_id=rq.delegate_id)

    votes = await delegate_vote_dao.list(0, 1, filters)

    print(filters)
    print(votes)

    if votes.count == 0:
        await delegate_vote_dao.create(
            VoteDelegateDB(**rq.dict(), user_id=user.id))
    else:
        vote = votes.items[0]
        vote.vote_value = rq.vote_value
        await delegate_vote_dao.update(vote)




class DelegateInfoResp(BaseModel):
    id: UUID4
    user_id: UUID4
    snt_alias: str
    street_name: str
    payer_id: str
    numsite: str
    phone: str
    first_name: str
    last_name: str
    grand_name: str
    value_for: int
    value_against: int
    value_abstained: int


@router.get('/delegates', description='Делегаты')
async def delegates(page: int = 0):
    delegates = await delegate_dao.list(0, 200, {})
    print(delegates)
    delegate_info_list = []

    #return [DelegateInfoResp(**(await personal_info_dao.list(0, 1, {'user_id': delegate.user_id})).items[0].dict(),
    #                         value_for=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_for',
    #                                                                           'delegate_id': delegate.user_id})).count,
    #                         value_against=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_against',
    #                                                                               'delegate_id': delegate.user_id})).count,
    #                         value_abstained=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_abstained',
    #                                                                                 'delegate_id': delegate.user_id})).count)
    #        for delegate in
    #        delegates.items]

    for delegate in delegates.items:
        user_info = await personal_info_dao.list(0, 1, {'user_id': delegate.user_id})
        if user_info.count > 0:
            delegate_info_list.append(DelegateInfoResp(**user_info.items[0].dict(),
                             value_for=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_for',
                                                                               'delegate_id': delegate.user_id})).count,
                             value_against=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_against',
                                                                                   'delegate_id': delegate.user_id})).count,
                             value_abstained=(await delegate_vote_dao.list(0, 1000, {'vote_value': 'value_abstained',
                                                                                     'delegate_id': delegate.user_id})).count))
    return delegate_info_list