from pydantic import Field, UUID4
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime
from enum import Enum

from backend_api.db.common import BaseDBModel
from backend_api.entities import PayStatus, Services


def now():
    return datetime.utcnow()

class ProblemTypes(str, Enum):
    public = 'public'
    private = 'private'

class TagNames(str, Enum):
    electricity = 'electricity'
    rubbish = 'rubbish'
    meeting = 'meeting'
    common_area = 'common_area'
    dogs = 'dogs'
    channel = 'channel'
    statute = 'statute'
    finance = 'finance'
    other = 'other'

class Statuses(str, Enum):
    new = 'new'
    process = 'process'
    done = 'done'

class ProblemDB(BaseDBModel):
    title: str
    problem_type: ProblemTypes
    tags: List[TagNames]
    status: Statuses
    responsible: UUID4
    docs: List[str] = []
    actions: List[str] = []
    created: datetime = Field(default_factory=now)
    problem_photos: List[str] = []
    problem_audios: List[str] = []
    problem_videos: List[str] = []
    comment_problem: str
    snt: str
    through: str
    geo_point: List[str]
    user_id: UUID4


class Importance(str, Enum):
    important = 'important'
    neutral = 'neutral'
    not_important = 'not_important'

class VoteDB(BaseDBModel):
    problem_id: UUID4
    user_id: UUID4
    importance: Importance
