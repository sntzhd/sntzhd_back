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
    default_data_url = 'https://storage.yandexcloud.net/sntzhd.ru/jsondata/streetListUrl/N1kZKVgpK'
    street_list_url = 'https://storage.yandexcloud.net/sntzhd.ru/jsondata/defaultDataUrl/EymrGfgTK'
    address_by_hash = 'https://storage.yandexcloud.net/www.auditsnt.ru/jsondata/address_by_hash/NypUu-4X9'


class YandexFunctionsConfig(BaseSettings):
    send_sms = 'https://functions.yandexcloud.net/d4e1i73pqlh396pps2ta'


mongo_config = MongoConfig()
secret_config = SecretConfig()
run_backend_api_config = RunConfigBackendAPI()
remote_service_config = RemoteServiceConfig()
yandex_functions_config = YandexFunctionsConfig()
