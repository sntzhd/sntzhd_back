import inject
from starlette.middleware.cors import CORSMiddleware

from . import app

from backend_api.injections import base

from backend_api.services.auth_service.endpoints import fastapi_users, jwt_authentication
from backend_api.utils import on_after_register

inject.configure(base)

origins = [
    'http://localhost',
    'http://localhost:4200',
    'https://receipts.ecom.net.ua',
    'http://130.193.59.212',
    'http://84.201.142.192',
    'https://auditsnt.ru',
    '130.193.59.212'
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def configure_routers():
    app.include_router(
        fastapi_users.get_register_router(on_after_register),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_auth_router(jwt_authentication),
        prefix="/auth/jwt",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_reset_password_router("SECRET"),
        prefix="/auth",
        tags=["auth"],
    )

    app.include_router(
        fastapi_users.get_users_router(),
        prefix="/users",
        tags=["users"],
    )


    from backend_api.endpoints import router
    from backend_api.problems.endpoints import router as router_problems

    app.include_router(router, prefix='/receipts', tags=["receipts"])
    app.include_router(router_problems, prefix='/problems', tags=["problems"])

configure_routers()
