from fastapi_users import FastAPIUsers, models
from fastapi_users.authentication import JWTAuthentication
from fastapi_users.db import MongoDBUserDatabase
from fastapi_users.models import BaseUserDB, BaseUserUpdate
from pymongo import uri_parser
import motor.motor_asyncio
from fastapi import FastAPI, Request
from pydantic import Field
#from db.users.models import UserBaseDB, UserBaseCreate, UserBase
from backend_api.entities import ReceiptEntity


from config import mongo_config, secret_config
from backend_api.utils import get_alias_info, get_street_id

db_name = uri_parser.parse_uri(mongo_config.URI)['database']
client = motor.motor_asyncio.AsyncIOMotorClient(mongo_config.URI)
print(uri_parser.parse_uri(mongo_config.URI))
db = client[db_name]
collection = db["users"]


user_db = MongoDBUserDatabase(BaseUserDB, collection)

auth_backends = []

jwt_authentication = JWTAuthentication(secret=secret_config.SECRET_KEY, lifetime_seconds=36)

auth_backends.append(jwt_authentication)

class User(models.BaseUser):
    #payer_id: str
    def __init__(self, **data):
        super().__init__(**data)



class UserCreate(models.BaseUserCreate):
    def __init__(self, **data):
        super().__init__(**data)
    #name: str
    #lastname: str
    #grandname: str
    #city: str
    #street: str
    #home: str
    #phone: str



class UserUpdate(User, models.BaseUserUpdate):
    def __init__(self, **data):
        super().__init__(**data)
    #payer_id: str



class UserDB(User, models.BaseUserDB):
    def __init__(self, **data):
        super().__init__(**data)
    #name: str
    #lastname: str
    #grandname: str
    #city: str
    #street: str
    #home: str
    #phone: str
    #payer_id: str = 'hhh'
    #is_delegate: bool = False

    #def __init__(self, **data):
    #    super().__init__(**data)
    #    alias = get_alias_info('sntzhd')
    #    street_id = get_street_id(ReceiptEntity(name='name', personal_acc='personal_acc',
    #                                            bank_name='bank_name', bic='bic', corresp_acc='corresp_acc', kpp='kpp',
    #                                            payee_inn='payee_inn', first_name='first_name', last_name='last_name',
    #                                            grand_name='grand_name', payer_address='payer_address', purpose='purpose',
    #                                            street=self.street, counter_type=1, rashod_t1=1, rashod_t2=1,
    #                                            t1_current=1, t1_paid=1, service_name='electricity', numsite='numsite',
    #                                           alias='sntzhd'))


    #    self.payer_id = payer_id = '{}-{}-{}'.format('2312088371'[4:8], street_id, self.home)
    #    #'{}{}'.format(data.get('street'), data.get('home'))
    #    print(data)


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
