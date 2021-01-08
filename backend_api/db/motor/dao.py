from decimal import Decimal
from typing import Type
from bson import DBRef, ObjectId

import pymongo
from bson import CodecOptions, Decimal128
from bson.codec_options import TypeRegistry, TypeCodec
from motor import motor_asyncio
from pymongo import uri_parser
from pydantic import BaseModel, UUID4

from config import mongo_config
from backend_api.interfaces import ResponseResult


class DataError(Exception):
    pass


class NotFoundError(DataError):
    pass


def get_db():
    config = mongo_config
    db_name = uri_parser.parse_uri(config.URI)['database']
    return motor_asyncio.AsyncIOMotorClient(config.URI)[db_name]


class DecimalCodec(TypeCodec):
    python_type = Decimal  # the Python type acted upon by this type codec
    bson_type = Decimal128  # the BSON type acted upon by this type codec

    def transform_python(self, value):
        """Function that transforms a custom type value into a type
       that BSON can encode."""
        return Decimal128(value)

    def transform_bson(self, value):
        """Function that transforms a vanilla BSON type value into our
        custom type."""
        return value.to_decimal()


class MotorGenericDAO:
    """works with db models(use it from app layer)"""

    def __init__(self, collection: str, model_cls: Type[BaseModel]):
        self._db = get_db()
        type_registry = TypeRegistry([DecimalCodec()])
        codec_options = CodecOptions(type_registry=type_registry)

        self._collection = self._db.get_collection(collection, codec_options=codec_options)
        self._collection.create_index("id", unique=True)
        self._model_cls = model_cls

    async def create(self, model: BaseModel):
        result = await self._collection.insert_one(model.dict())
        if result.inserted_id:
            return model.id

    async def get(self, id_: UUID4):
        record = await self._collection.find_one({"id": id_})

        records = await self._collection.find({}).to_list(10)

        if record is None:
            raise NotFoundError(f'Not found {self._model_cls} with id {id_}!')
        return self._model_cls(**record)

    async def update(self, model: BaseModel):
        result = await self._collection.update_one({"id": model.id}, {'$set': model.dict(exclude_unset=True)})
        return bool(result.modified_count)

    async def delete(self, id_: UUID4):
        record = await self._collection.delete_one({"id": id_})
        if record is None:
            raise NotFoundError(f'Not found {self._model_cls} with id {id_}!')

    async def list(self, skip, limit, filters) -> ResponseResult:

        records = await self._collection.find(filters).sort('_id', pymongo.DESCENDING) \
            .skip(skip).limit(limit).to_list(limit)

        total = await self.count_total(filters)
        return ResponseResult(items=[self._model_cls(**r) for r in records], count=total)

    async def all(self, filters={}):
        records = await self._collection.find(filters).sort('_id', pymongo.DESCENDING).to_list(None)

        if records:
            return [self._model_cls(**r) for r in records]
        return []

    async def count_total(self, filters={}):
        return await self._collection.count_documents(filters)


def dao_creator(collection: str, model_cls: Type[BaseModel]):
    return MotorGenericDAO(collection, model_cls)
