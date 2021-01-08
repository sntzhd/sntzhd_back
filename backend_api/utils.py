from typing import TYPE_CHECKING
import inject
from datetime import datetime
from uuid import uuid4

from typing import Type, TypeVar

T = TypeVar('T')


def instance(cls: Type[T]) -> T:
    inst: cls = inject.instance(cls)
    if TYPE_CHECKING:
        assert isinstance(inst, cls)
    return inst


def create_id():
    return uuid4()


def now():
    return datetime.utcnow()
