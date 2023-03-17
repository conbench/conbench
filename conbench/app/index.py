from collections import defaultdict


from dataclasses import dataclass


from typing import Optional

import flask as f

from sqlalchemy import select

from ..db import Session
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.benchmarks import RunMixin
from ..config import Config
from ..entities.run import Run


class Index(AppEndpoint, RunMixin):
    def page(self, runs):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            runs=runs,
            search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self):
        return self.page(runs)
        # Following
        # https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities
        runs = Session.scalars(
            select(Run).order_by(Run.timestamp.desc()).limit(1000)
        ).all()




view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
