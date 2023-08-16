import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

import flask

import conbench.util

from ..api.runs import get_all_run_info
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.results import RunMixin
from ..config import Config
from ..entities.benchmark_result import BenchmarkResult

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
    def get(self) -> str | flask.Response:
        resp = _cloud_lb_health_check_shortcut()
        if resp is not None:
            return resp

        # Get run info from benchmark results in the last 30 days.
        all_run_info = get_all_run_info(
            min_time=datetime.datetime.utcnow() - datetime.timedelta(days=30),
            max_time=datetime.datetime.utcnow(),
        )
        # Note(JP): group runs by associated commit.repository value.
        reponame_runs_map: Dict[str, List[RunForDisplay]] = defaultdict(list)

        for benchmark_result, count, any_failures in all_run_info:
            # Note: At the "30d ago" boundary, the count is permanently wrong (single
            # run partially represented in DB query result, true for just one of many
            # runs). That's fine, the UI does not claim real-time truth in that regard.
            # In the vast majority of the cases we get a correct result count per run.
            result_count = str(count)

            rd = RunForDisplay(
                ctime_for_table=benchmark_result.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
                commit_message_short=conbench.util.short_commit_msg(
                    benchmark_result.commit.message if benchmark_result.commit else ""
                ),
                result_count=result_count,
                any_benchmark_results_failed=any_failures,
                result=benchmark_result,
            )

            rname = repo_url_to_display_name(
                benchmark_result.associated_commit_repo_url
            )
            reponame_runs_map[rname].append(rd)

        # A quick decision for now, not set in stone: get a stable sort order
        # of repositories the way they are listed on that page; do this by
        # sorting alphabetically.
        reponame_runs_map_sorted = dict(sorted(reponame_runs_map.items()))

        # Those runs without repo information "n/a" should for now not
        # be at the top. Move this to the end of the (ordered) dict.
        # See https://github.com/conbench/conbench/issues/1226
        if "n/a" in reponame_runs_map_sorted:
            reponame_runs_map_sorted["n/a"] = reponame_runs_map_sorted.pop("n/a")

        return self.page(reponame_runs_map_sorted)


def repo_url_to_display_name(url: Optional[str]) -> str:
    if url is None:
        # For those cases where the repository information stored with a
        # Commit object in the DB is not a URL
        return "no repository specified"

    try:
        result = urlparse(url)
    except ValueError as exc:
        log.warning("repo_url failed urlparse(): %s, %s", url, exc)
        # In this case, don't care about cosmetics: display the 'raw' data.
        return url

    p = result.path

    # See https://github.com/conbench/conbench/issues/1095
    if isinstance(p, bytes):
        # Note: this case can be hit when `url` is None! Interesting.
        log.info("repo_url_to_display_name led to bytes obj: url: %s", url)
        p = p.decode("utf-8")

    if p == "":
        # In this case, don't care about cosmetics: display the 'raw' data.
        return url

    # A common case is that there now is a leading slash. Remove that. Note
    # that `strip()` also operates on the trailing end. I think there shouldn't
    # be a trailing slash, but if it's there, remove it, too.
    return p.strip("/")


@dataclass
class RunForDisplay:
    ctime_for_table: str
    commit_message_short: str
    result_count: str | int
    any_benchmark_results_failed: bool
    # Expose the (earliest) raw BenchmarkResult object (but this needs to be used with a
    # lot of care, in the template -- for VSCode supporting Python variable types and
    # auto-completion in a jinja2 template see
    # https://github.com/microsoft/pylance-release/discussions/4090)
    result: BenchmarkResult


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
