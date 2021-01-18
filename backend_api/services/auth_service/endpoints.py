from fastapi_users import FastAPIUsers, models
from fastapi_users.authentication import JWTAuthentication
from fastapi_users.db import MongoDBUserDatabase
from fastapi_users.models import BaseUserDB, BaseUserUpdate
from pymongo import uri_parser
import motor.motor_asyncio
from fastapi import FastAPI, Request
#from db.users.models import UserBaseDB, UserBaseCreate, UserBase

from config import mongo_config, secret_config

db_name = uri_parser.parse_uri(mongo_config.URI)['database']
client = motor.motor_asyncio.AsyncIOMotorClient(mongo_config.URI)
print(uri_parser.parse_uri(mongo_config.URI))
db = client[db_name]
collection = db["users"]


user_db = MongoDBUserDatabase(BaseUserDB, collection)

auth_backends = []

jwt_authentication = JWTAuthentication(secret=secret_config.SECRET_KEY, lifetime_seconds=3600)

auth_backends.append(jwt_authentication)

class User(models.BaseUser):
    payer_id: str



class UserCreate(models.BaseUserCreate):
    name: str
    lastname: str
    grandname: str
    city: str
    street: str
    home: str
    phone: str



class UserUpdate(User, models.BaseUserUpdate):
    pass


class UserDB(User, models.BaseUserDB):
    name: str
    lastname: str
    grandname: str
    city: str
    street: str
    home: str
    phone: str
    payer_id: str


def on_after_register(user: UserDB, request: Request):
    print(f"User {user.id} has registered.")


def on_after_forgot_password(user: UserDB, token: str, request: Request):
    print(f"User {user.id} has forgot their password. Reset token: {token}")


jwt_authentication = JWTAuthentication(
    secret=secret_config.SECRET_KEY, lifetime_seconds=3600, tokenUrl="/auth/jwt/login"
)


fastapi_users = FastAPIUsers(
    user_db,
    [jwt_authentication],
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)
