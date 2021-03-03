from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel
from typing import List

from backend_api.interfaces import IProblemDAO, IVoteDAO
from backend_api.db.problems.models import ProblemTypes, TagNames, Statuses, ProblemDB, Importance, VoteDB
from backend_api.services.auth_service.endpoints import fastapi_users
from backend_api.utils import instance
from backend_api.entities import ListResponse

HISTORY_PAGE_SIZE = 20

problem_dao: IProblemDAO = instance(IProblemDAO)
vote_dao: IVoteDAO = instance(IVoteDAO)

router = APIRouter()


class ProblemRq(BaseModel):
    title: str
    problem_type: ProblemTypes
    tags: List[TagNames]
    status: Statuses
    docs: List[str] = []
    actions: List[str] = []
    problem_photos: List[str] = []
    problem_audios: List[str] = []
    problem_videos: List[str] = []
    comment_problem: str
    snt: str
    through: str
    geo_point: List[str]


@router.post('/report-problem', description='Сообщить о проблеме')
async def report_problem(rq: ProblemRq, user=Depends(fastapi_users.get_current_user)):
    await problem_dao.create(ProblemDB(**rq.dict(), responsible=user.id, user_id=user.id))


@router.get('/problems', description='Проблемы')
async def problems(page: int = 0, user=Depends(fastapi_users.get_current_user)):
    skip = page * HISTORY_PAGE_SIZE

    filters = dict()
    problems = await problem_dao.list(skip, HISTORY_PAGE_SIZE, filters)
    return ListResponse(items=problems.items, count=problems.count)

class VoteRq(BaseModel):
    problem_id: UUID4
    importance: Importance

@router.post('/to-vote', description='Проголосовать')
async def to_vote(rq: VoteRq, user=Depends(fastapi_users.get_current_user)):
    filters = dict(user_id=user.id)

    votes = await vote_dao.list(0, 1, filters)

    if votes.count == 0:
        await vote_dao.create(VoteDB(**rq.dict(), user_id=user.id))
    else:
        vote = votes.items[0]
        vote.importance = rq.importance
        await vote_dao.update(vote)
