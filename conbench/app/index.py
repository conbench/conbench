import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import flask
from sqlalchemy import select

import conbench.util

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.results import RunMixin
from ..config import Config
from ..db import Session
from ..entities.run import Run

log = logging.getLogger(__name__)


def _cloud_lb_health_check_shortcut() -> Optional[flask.Response]:
    # Pragmatic short-cut for
    # https://github.com/conbench/conbench/issues/1007
    ua = flask.request.headers.get("User-Agent")
    if ua:
        if "HealthChecker" in ua:
            return flask.make_response(("thanks, we're good", 200))

    # Explicit None.
    return None


class Index(AppEndpoint, RunMixin):
    def page(self, repo_runs_map):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            repo_runs_map=repo_runs_map,
            # Note(JP): search_value is not consumed in template
            # search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self):
        resp = _cloud_lb_health_check_shortcut()
        if resp is not None:
            return resp

        # Following
        # https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities
        runs = Session.scalars(
            select(Run).order_by(Run.timestamp.desc()).limit(1000)
        ).all()

        # Note(JP): group runs by associated commit.repository value. Note that
        # consistency between benchmark results in the run is currently not
        # granted: https://github.com/conbench/conbench/issues/864

        reponame_runs_map = defaultdict(list)

        for r in runs:
            rd = RunForDisplay(
                ctime_for_table=r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                commit_message_short=conbench.util.short_commit_msg(r.commit.message),
                # Temporary band-aid; we cannot fetch all last-1000-run-related
                # BenchmarkResult objects each time we render the landing page.
                # See https://github.com/conbench/conbench/issues/977 However,
                # we will find a pragmatic way to still display a per-run
                # result count (estimate). I want to leave this code intact for
                # now and display a placeholder.
                result_count="",
                run=r,
            )

            rname = repo_url_to_display_name(r.commit.repo_url)
            reponame_runs_map[rname].append(rd)

        # A quick/pragmatic decision for now, not set in stone: get a stable
        # sort order of repositories the way they are listed on that page;
        # do this by sorting alphabetically.
        reponame_runs_map = dict(sorted(reponame_runs_map.items()))

        return self.page(reponame_runs_map)


def repo_url_to_display_name(url: str) -> str:
    try:
        result = urlparse(url)
    except ValueError as exc:
        log.warning("repo_url failed urlparse(): %s, %s", url, exc)
        # In this case, don't care about cosmetics: display the 'raw' data.
        return url

    if result.path == "":
        # In this case, don't care about cosmetics: display the 'raw' data.
        return url

    # A common case is that there now is a leading slash. Remove that. Note
    # that `strip()` also operates on the trailing end. I think there shouldn't
    # be a trailing slash, but if it's there, remove it, too.
    return result.path.strip("/")


@dataclass
class RunForDisplay:
    ctime_for_table: str
    commit_message_short: str
    result_count: str | int
    # Expose the raw Run object (but this needs to be used with a lot of
    # care, in the template -- for VSCode supporting Python variable types and
    # auot-completion in a jinja2 template see
    # https://github.com/microsoft/pylance-release/discussions/4090)
    run: Run


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
