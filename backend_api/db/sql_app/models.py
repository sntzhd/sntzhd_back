import peewee

from .database import db


class Item(peewee.Model):
    name = peewee.CharField()
    personal_account = peewee.CharField()

    class Meta:
        database = db
