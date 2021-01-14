import inject
from starlette.middleware.cors import CORSMiddleware

from . import app

from backend_api.injections import base

from backend_api.services.auth_service.endpoints import fastapi_users, jwt_authentication

inject.configure(base)

origins = [
    'http://localhost',
    'http://localhost:4200',
    'https://receipts.ecom.net.ua'
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
        fastapi_users.get_register_router(),
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

    app.include_router(router, prefix='/receipts', tags=["receipts"])


configure_routers()
