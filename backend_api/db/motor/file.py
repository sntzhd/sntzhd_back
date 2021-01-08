from bson import ObjectId
from gridfs import NoFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from backend_api.db.exceptions import NotFoundError
from backend_api.db.motor.dao import get_db

from abc import abstractmethod, ABCMeta


class IFileDAO(metaclass=ABCMeta):
    @abstractmethod
    def get(self, id_):
        pass

    @abstractmethod
    def add(self, file):
        pass


class FileDAO(IFileDAO):
    def __init__(self):
        super().__init__()
        self._db = get_db()
        self.fs = AsyncIOMotorGridFSBucket(self._db)

    async def get(self, id_):
        try:
            return await self.fs.open_download_stream(ObjectId(id_))
        except NoFile:
            raise NotFoundError(f'File not found: {id_}')

    async def add(self, file):
        file_id = await self.fs.upload_from_stream(
            file.filename,
            await file.read(),
            chunk_size_bytes=4,
            metadata={"contentType": file.content_type})
        return str(file_id)
