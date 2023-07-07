import functools
from typing import Dict, Generic, List, Type, TypeVar

import flask as f
import sqlalchemy
from sqlalchemy import distinct, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import declarative_base, mapped_column
from sqlalchemy.orm.exc import NoResultFound

# Use stdlib once that's there:
# https://github.com/python/cpython/issues/102461
from uuid_extensions import uuid7

from conbench.dbsession import current_session

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


def genprimkey():
    """
    Return a UUID type 7 as a 32-character lowercase hexadecimal string.

    The main purpose is that that the primary key used for DB entities
    can be used to sort by insertion time.

    See https://github.com/conbench/conbench/issues/789.

    https://uuid.ramsey.dev/en/stable/rfc4122/version7.html

    'Version 7 UUIDs are binary-compatible with ULIDs (universally unique
    lexicographically-sortable identifiers).'

    'Version 7 UUIDs combine random data (like version 4 UUIDs) with a
    timestamp (in milliseconds since the Unix Epoch, i.e., 1970-01-01 00:00:00
    UTC) to create a monotonically increasing, sortable UUID that doesn’t have
    any privacy concerns, since it doesn’t include a MAC address.'

    Note(JP): maybe we still allow user-given data to be used as primary key,
    that of course undermines the idea expressed above. Step by step.
    """
    return uuid7().hex


def to_float(value):
    return float(value) if value is not None else None


T = TypeVar("T")


class EntityMixin(Generic[T]):
    """ """

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"

    @classmethod
    def count(cls):
        return current_session.query(cls).count()

    @classmethod
    def distinct(cls, column, filters):
        q = current_session.query(distinct(column))
        return q.filter(*filters).all()

    @classmethod
    def search(cls, filters, joins=None, order_by=None, limit=None):
        q = current_session.query(cls)
        if joins:
            for join in joins:
                q = q.join(join)
        if order_by is not None:
            q = q.order_by(order_by)

        if limit is None:
            return q.filter(*filters).all()

        return q.filter(*filters).limit(limit).all()

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
        # when invoked via the current_session.execute() method will return
        # ORM-oriented results, that is, ORM objects if that’s what was
        # requested.""
        query = current_session.query(cls)
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
        return current_session.get(cls, _id)

    @classmethod
    def one(cls, **kwargs):
        try:
            return current_session.query(cls).filter_by(**kwargs).one()
        except NoResultFound:
            raise NotFound()

    @classmethod
    def first(cls, **kwargs):
        return current_session.scalars(select(cls).filter_by(**kwargs)).first()

    @classmethod
    def delete_all(cls):
        current_session.query(cls).delete()
        current_session.commit()

    @classmethod
    def create(cls, data):
        entity = cls(**data)
        entity.save()
        return entity

    @classmethod
    def upsert_do_nothing(cls, row_list: List[dict]):
        """Try to insert rows. If there is a conflict on any row, ignore that row."""
        statement = postgresql_insert(cls).values(row_list).on_conflict_do_nothing()
        current_session.execute(statement)
        current_session.commit()

    @classmethod
    def bulk_save_objects(self, bulk):
        current_session.bulk_save_objects(bulk)
        current_session.commit()

    def update(self, data):
        for field, value in data.items():
            setattr(self, field, value)
        self.save()

    def save(self):
        current_session.add(self)
        current_session.commit()

    def delete(self):
        current_session.delete(self)
        current_session.commit()

    @classmethod
    def get_or_create(cls: Type[T], props: Dict) -> T:
        """
        Try to create, but expect conflict (work with unique constraint on name/tags).

        Return (newly created, or previously existing) object, or raise an exception.

        If there is no unique constraint on the keys of props, race conditions will
        result in duplicated rows, but should not fail. This should be rare.
        """

        def _fetch_first():
            return current_session.scalars(select(cls).filter_by(**props)).first()

        result = _fetch_first()
        if result is not None:
            return result

        obj = cls(**props)
        obj.post_init_pre_add()
        current_session.add(obj)
        try:
            current_session.commit()
            return obj
        except sqlalchemy.exc.IntegrityError as exc:
            if "violates unique constraint" not in str(exc):
                raise

        # When we end up here it means that a unique key constraint was
        # violated. We did hit a narrow race condition: query failed, creation
        # failed. Query again.
        current_session.rollback()
        result = _fetch_first()
        assert result is not None
        return result

    def post_init_pre_add(self):
        """Override this method to do any initialization before adding to the session
        when using get_or_create().
        """
        pass


class EntitySerializer:
    def __init__(self, many=None):
        self.many = many

    def dump(self, data):
        if self.many:
            return f.jsonify([self._dump(row) for row in data])
        else:
            return self._dump(data)
