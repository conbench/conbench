import functools
import uuid
from typing import List

import flask as f
from sqlalchemy import distinct
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import declarative_base, mapped_column
from sqlalchemy.orm.exc import NoResultFound

from ..db import Session

Base = declarative_base()
NotNull = functools.partial(mapped_column, nullable=False)
Nullable = functools.partial(mapped_column, nullable=True)


class NotFound(NoResultFound):
    pass


class EntityExists(Exception):
    """
    Custom exception representing a database conflict. Meant to be caught from
    within HTTP request handlers, and to be translated into an HTTP response
    with status code 409. The `msg` in `raise EntityExists(msg)` is meant to be
    exposed directly to the HTTP client (that is, construct it mindfully: do
    not expose meaningless detail).
    """

    pass


def generate_uuid():
    # Consider using xid or UUID7 or something comparable so that primary
    # key reflects insertion order.
    return uuid.uuid4().hex


def to_float(value):
    return float(value) if value is not None else None


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
    def search(cls, filters, joins=None, order_by=None):
        q = Session.query(cls)
        if joins:
            for join in joins:
                q = q.join(join)
        if order_by is not None:
            q = q.order_by(order_by)
        return q.filter(*filters).all()

    @classmethod
    def all(cls, limit=None, order_by=None, filter_args=None, **kwargs):
        """Filter using filter_args and/or kwargs. If you just need WHERE x = y, you can
        use kwargs, e.g. ``all(x=y)``. Else if you need something more complicated, use
        e.g. ``all(filter_args=[cls.x != y])``.
        """
        # Note(JP): This is now a legacy technique, see
        #  https://docs.sqlalchemy.org/en/20/changelog/migration_20.html#orm-query-unified-with-core-select
        # "The Query object (as well as the BakedQuery and ShardedQuery
        # extensions) become long term legacy objects, replaced by the direct
        # usage of the select() [...] Because the vast majority of an ORM
        # application is expected to make use of Query objects as well as that
        # the Query interface being available does not impact the new
        # interface, the object will stay around in 2.0 but will no longer be
        # part of documentation nor will it be supported for the most part. The
        # select() construct now suits both the Core and ORM use cases, which
        # when invoked via the Session.execute() method will return
        # ORM-oriented results, that is, ORM objects if that’s what was
        # requested.""
        query = Session.query(cls)
        if filter_args:
            query = query.filter(*filter_args)
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
    def upsert_do_nothing(cls, row_list: List[dict]):
        """Try to insert rows. If there is a conflict on any row, ignore that row."""
        statement = postgresql_insert(cls).values(row_list).on_conflict_do_nothing()
        Session.execute(statement)
        Session.commit()

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
