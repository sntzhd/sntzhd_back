from . import models, schemas

def create_item(item: schemas.ItemBase):
    print(item.dict())
    db_item = models.Item(**item.dict())
    db_item.save()
    print(db_item)
    return db_item