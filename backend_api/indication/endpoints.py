from fastapi import Depends, FastAPI, HTTPException, APIRouter

from backend_api.db.sql_app import crud, database, models, schemas
from backend_api.db.sql_app.database import db_state_default

database.db.connect()
database.db.create_tables([models.Item])
database.db.close()

router = APIRouter()

async def reset_db_state():
    database.db._state._state.set(db_state_default.copy())
    database.db._state.reset()

def get_db(db_state=Depends(reset_db_state)):
    try:
        database.db.connect()
        yield
    finally:
        if not database.db.is_closed():
            database.db.close()


@router.post(
    "/items/",
    response_model=schemas.ItemBase,
    dependencies=[Depends(get_db)],
)
def create_item_for_user(item: schemas.ItemBase):
    return crud.create_item(item=item)