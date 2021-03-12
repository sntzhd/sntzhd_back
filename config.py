from pydantic import BaseSettings


class MongoConfig(BaseSettings):
    URI: str

    class Config:
        env_file = '.env'


class SecretConfig(BaseSettings):
    SECRET_KEY: str
    SMS_SERVIE_ID: str
    SEND_SMS: bool

    class Config:
        env_file = '.env'

class RunConfigBackendAPI(BaseSettings):
    HOST: str = '0.0.0.0'
    PORT: int = 5555
    DEV: bool = True

    class Config:
        env_file = '.env'

class RemoteServiceConfig(BaseSettings):
    default_data_url = 'https://next.json-generator.com/api/json/get/EymrGfgTK'
    street_list_url = 'https://next.json-generator.com/api/json/get/VyJpUsP-q'
    address_by_hash = 'https://next.json-generator.com/api/json/get/NypUu-4X9'

mongo_config = MongoConfig()
secret_config = SecretConfig()
run_backend_api_config = RunConfigBackendAPI()
remote_service_config = RemoteServiceConfig()

