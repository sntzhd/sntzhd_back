from abc import abstractmethod, ABCMeta
from pydantic import BaseModel
from typing import List


class IGenericDAO(metaclass=ABCMeta):
    @abstractmethod
    def create(self, model: BaseModel):
        pass

    @abstractmethod
    def get(self, id_: str):
        pass

    @abstractmethod
    def update(self, model: BaseModel):
        pass

    @abstractmethod
    def delete(self, model: BaseModel):
        pass

    @abstractmethod
    def list(self, skip, limit, filters):
        pass

    @abstractmethod
    def all(self):
        pass

    @abstractmethod
    def count_total(self):
        pass


class ResponseResult(BaseModel):
    items: List[BaseModel]
    count: int


class IReceiptDAO(IGenericDAO):
    pass

class IPersonalInfoDAO(IGenericDAO):
    pass

class IBonusAccDAO(IGenericDAO):
    pass

class IBonusHistoryDAO(IGenericDAO):
    pass

class IDelegateDAO(IGenericDAO):
    pass

class IDelegateEventDAO(IGenericDAO):
    pass

class ICheckingNumberDAO(IGenericDAO):
    pass

class IProblemDAO(IGenericDAO):
    pass

class IVoteDAO(IGenericDAO):
    pass

class IDelegatActionDAO(IGenericDAO):
    pass

class IVoteDelegateDAO(IGenericDAO):
    pass