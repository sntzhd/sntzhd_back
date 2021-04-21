from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from pydantic import UUID4, BaseModel
from typing import List, Any, Optional, Dict
import requests

from backend_api.interfaces import IProblemDAO, IVoteDAO
from backend_api.db.problems.models import ProblemTypes, TagNames, Statuses, ProblemDB, Importance, VoteDB
from backend_api.services.auth_service.endpoints import fastapi_users
from backend_api.utils import instance
from backend_api.entities import ListResponse
from config import remote_service_config
from backend_api.static_data import url_streets

HISTORY_PAGE_SIZE = 20

problem_dao: IProblemDAO = instance(IProblemDAO)
vote_dao: IVoteDAO = instance(IVoteDAO)

router = APIRouter()


class ProblemRq(BaseModel):
    title: str
    problem_type: ProblemTypes
    tags: List[TagNames]
    docs: List[Any] = []
    problem_photos: List[Any] = []
    problem_audios: List[Any] = []
    problem_videos: List[Any] = []
    comment_problem: Optional[str]
    snt: str
    through: str
    geo_point: List[str]
    street: Optional[str]


@router.post('/report-problem', description='Сообщить о проблеме')
async def report_problem(rq: ProblemRq, user=Depends(fastapi_users.get_current_user)) -> UUID4:
    id_ = await problem_dao.create(ProblemDB(**rq.dict(), status='new', responsible=user.id, user_id=user.id))
    return id_


class ProblemResp(ProblemDB):
    important: int
    neutral: int
    not_important: int
    my_voice: Optional[str]


@router.get('/problems', description='Проблемы')
async def problems(page: int = 0, user=Depends(fastapi_users.get_current_user)):
    skip = page * HISTORY_PAGE_SIZE

    r_streets = requests.get(url_streets, verify=False)


    if user.is_superuser:
        filters = dict()
        problems = await problem_dao.list(skip, HISTORY_PAGE_SIZE, filters)
        return ListResponse(items=problems.items, count=problems.count)
    else:
        filters = {'$or': [{'user_id': user.id}, {'problem_type': 'public'}]}
        problems = await problem_dao.list(skip, HISTORY_PAGE_SIZE, filters)

        resp_problems: List[ProblemResp] = []

        for problem in problems.items:
            filters = dict(problem_id=problem.id)
            important = 0
            neutral = 0
            not_important = 0
            my_voice = None
            votes = await vote_dao.list(0, 1, filters)
            print(problem.street)

            for street in r_streets.json().get('sntList')[0].get('streetList'):
                if problem.street == str(street.get('strID')):
                    problem.street = street.get('strName')

            my_voices = await vote_dao.list(0, 1, dict(problem_id=problem.id, user_id=user.id))
            if my_voices.count > 0:
                my_voice = my_voices.items[0].importance
            for vote in votes.items:
                if vote.importance.value == 'important':
                    important += 1

                if vote.importance.value == 'neutral':
                    neutral += 1

                if vote.importance.value == 'not_important':
                    not_important += 1
            if len(problem.problem_photos) > 0:
                img_url = 'https://storage.yandexcloud.net/functions-yandex/image2bucket/{}.jpg'
                problem.problem_photos = [img_url.format(p) for p in problem.problem_photos]
                #print(problem.problem_photos)

            resp_problems.append(ProblemResp(**problem.dict(), important=important, neutral=neutral,
                                             not_important=not_important, my_voice=my_voice))

        return ListResponse(items=resp_problems, count=problems.count)


class VoteRq(BaseModel):
    problem_id: UUID4
    importance: Importance


class VoteResp(BaseModel):
    Reply: str
    function: str
    response: Dict[str, str]


@router.post('/to-vote', description='Проголосовать')
async def to_vote(rq: VoteRq, user=Depends(fastapi_users.get_current_user)):
    filters = dict(user_id=user.id, problem_id=rq.problem_id)

    votes = await vote_dao.list(0, 1, filters)

    if votes.count == 0:
        await vote_dao.create(VoteDB(**rq.dict(), user_id=user.id))
    else:
        vote = votes.items[0]
        vote.importance = rq.importance
        await vote_dao.update(vote)

    return VoteResp(Reply='Ok', function='voteToProblem', response=dict(problem_id=str(rq.problem_id), importance=rq.importance))



@router.get('/coordinates-by-street-id', )
async def coordinates_by_street_id(street_id: str) -> List[str]:
    r = requests.get(remote_service_config.street_list_url)
    for street in r.json().get('sntList')[0].get('streetList'):
        if str(street.get('strID')) == street_id:
            return street.get('geometry').get('coordinates')[0]


@router.get('/problem', description='Проблема')
async def problem(problem_id: UUID4, user=Depends(fastapi_users.get_current_user)) -> ProblemDB:
    problem = await problem_dao.get(problem_id)
    important = 0
    neutral = 0
    not_important = 0
    my_voice = None
    votes = await vote_dao.list(0, 1, dict(problem_id=problem.id))
    my_voices = await vote_dao.list(0, 1, dict(problem_id=problem.id, user_id=user.id))
    if my_voices.count > 0:
        my_voice = my_voices.items[0].importance
    for vote in votes.items:
        if vote.importance.value == 'important':
            important += 1

        if vote.importance.value == 'neutral':
            neutral += 1

        if vote.importance.value == 'not_important':
            not_important += 1

    r_streets = requests.get(url_streets, verify=False)

    for street in r_streets.json().get('sntList')[0].get('streetList'):
        if problem.street == str(street.get('strID')):
            problem.street = street.get('strName')


    return ProblemResp(**problem.dict(), important=important, neutral=neutral,
                       not_important=not_important, my_voice=my_voice)
