import functools
import uuid

import flask as f
from sqlalchemy import Column, distinct
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.exc import NoResultFound

from ..db import Session

Base = declarative_base()
NotNull = functools.partial(Column, nullable=False)
Nullable = functools.partial(Column, nullable=True)


class NotFound(NoResultFound):
    pass


def generate_uuid():
    return uuid.uuid4().hex


class EntityMixin:
    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"

    @classmethod
    def count(cls):
        return Session.query(cls).count()

    @classmethod
    def distinct(cls, column, filters):
        q = Session.query(distinct(column))
        return q.filter(*filters).all()

    @classmethod
    def search(cls, filters, joins=None):
        q = Session.query(cls)
        if joins:
            for join in joins:
                q = q.join(join)
        return q.filter(*filters).all()

    @classmethod
    def all(cls, limit=None, order_by=None, **kwargs):
        query = Session.query(cls)
        if kwargs:
            query = query.filter_by(**kwargs)
        if order_by is not None:
            query = query.order_by(order_by)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def get(cls, _id):
        return Session().get(cls, _id)

    @classmethod
    def one(cls, **kwargs):
        try:
            return Session.query(cls).filter_by(**kwargs).one()
        except NoResultFound:
            raise NotFound()

    @classmethod
    def first(cls, **kwargs):
        return Session.query(cls).filter_by(**kwargs).first()

    @classmethod
    def delete_all(cls):
        Session.query(cls).delete()
        Session.commit()

    @classmethod
    def create(cls, data):
        entity = cls(**data)
        entity.save()
        return entity

    @classmethod
    def bulk_save_objects(self, bulk):
        Session.bulk_save_objects(bulk)
        Session.commit()

    def update(self, data):
        for field, value in data.items():
            setattr(self, field, value)
        self.save()

    def save(self):
        Session.add(self)
        Session.commit()

    def delete(self):
        Session.delete(self)
        Session.commit()


class EntitySerializer:
    def __init__(self, many=None):
        self.many = many

    def dump(self, data):
        if self.many:
            return f.jsonify([self._dump(row) for row in data])
        else:
            return self._dump(data)
