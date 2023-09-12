import logging
from collections import defaultdict
from typing import Dict, List, Optional
from urllib.parse import urlparse

import flask

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.results import RunMixin
from ..config import Config
from ..entities.benchmark_result import BenchmarkResult, one_result_per_n_recent_runs

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
    def page(self, reponame_result_map_sorted):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            reponame_result_map_sorted=reponame_result_map_sorted,
            # Note(JP): search_value is not consumed in template
            # search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self) -> str | flask.Response:
        resp = _cloud_lb_health_check_shortcut()
        if resp is not None:
            return resp

        # Get (any?) one result for all of the N most recently seen run IDs.
        # This is not necessarily the earliest result. It may be, as of the
        # current implementation, but this isn't guaranteed for now. Also, as
        # of the DB query used we cannot answer if "any result in this run
        # failed?", i.e. the notion of "a failed run" is not on the UI landing
        # page anymore.
        bmrs = one_result_per_n_recent_runs()

        # Note(JP): group one-result-per-run by associated repository value.
        reponame_result_map: Dict[str, List[BenchmarkResult]] = defaultdict(list)

        for r in bmrs:
            rname = repo_url_to_display_name(r.commit_repo_url)
            reponame_result_map[rname].append(r)

        # A quick decision for now, not set in stone: get a stable sort order
        # of repositories the way they are listed on that page; do this by
        # sorting alphabetically.
        reponame_result_map_sorted = dict(sorted(reponame_result_map.items()))

        # log.info(reponame_result_map_sorted)

        return self.page(reponame_result_map_sorted)


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


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
