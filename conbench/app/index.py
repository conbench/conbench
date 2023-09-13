import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

import flask

from conbench.bmrt import bmrt_cache
from conbench.cachetools import lru_cache_with_ttl

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.results import RunMixin
from ..config import Config
from ..entities.benchmark_result import fetch_one_result_per_n_recent_runs
from ..entities.commit import Commit

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
    def page(self, reponame_runs_map_sorted):
        return self.render_template(
            "index.html",
            application=Config.APPLICATION_NAME,
            title="Home",
            reponame_runs_map_sorted=reponame_runs_map_sorted,
            # Note(JP): search_value is not consumed in template
            # search_value=f.request.args.get("search"),
        )

    @authorize_or_terminate
    def get(self) -> str | flask.Response:
        resp = _cloud_lb_health_check_shortcut()
        if resp is not None:
            return resp

        # _get_recent_runs() uses a return value cache base don the stdlib LRU
        # cache module. Clear that cache during testing; the lru_cache
        # decorator has added a `cache_clear()` method to the func object.
        if Config.TESTING:
            _get_recent_runs.cache_clear()
        runs_for_display = _get_recent_runs()

        # Note(JP): group one-result-per-run by associated repository value.
        reponame_rd_map: Dict[str, List[RunForDisplay]] = defaultdict(list)

        for rd in runs_for_display:
            reponame = repo_url_to_display_name(rd.repo_url)
            reponame_rd_map[reponame].append(rd)

        # A quick decision for now, not set in stone: get a stable sort order
        # of repositories the way they are listed on that page; do this by
        # sorting alphabetically.
        reponame_runs_map_sorted = dict(sorted(reponame_rd_map.items()))
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


# Cache the return value for the last few minutes minutes. See docstring for
# discussion. In local dev with only few results / runs in the database this
# cache reduces landing page response generation time from 300 ms to 10 ms.
# This cache applies to all request-serving threads in this gunicorn worker
# process (each single-process container replica maintains its own cache).
@lru_cache_with_ttl(ttl=300)
def _get_recent_runs() -> List["RunForDisplay"]:
    """
    As of the time of writing, the UI landing page wants to show the "N most
    recent CI runs". Since removal of the Run table we still want retain that.

    For now, we do this by getting (any) one result for all of the N most
    recently seen run IDs (each CI run may be associated with O(10**3) results;
    it is therefore not feasible to fetch all last-bigN-run-related
    BenchmarkResult objects each time we render the landing page).

    Ideally, with the "one result row per run" approach, a single small-ish DB
    query response yields _all_ data necessary to display information about the
    N most recently seen CI runs. However, there are limitations to this
    approach.

    -  The one result-per-run that we get from the DB is not necessarily the
       earliest result. It may be, as of the current implementation, but this
       isn't guaranteed for now. The meaning of "time" for a Run is a bit
       ambiguous (albeit, still useful). Assumption: around the time where this
       one result was submitted, all other results for the same run were
       submitted, too.

    -  As of the DB query used we cannot answer if "any result in this run
       failed?". That is, the notion of "a failed run" is not currently on the
       UI landing page anymore. We discussed that this is okay; an expected
       outcome as of not representing each CI run in its own DB table anymore.

    -  Letting the DB count results-per-run easily is too much work. Also see
       https://github.com/conbench/conbench/issues/977. However, the BMRT cache
       (built for other purpose) knows a per-run result count estimate for many
       of the most recent runs. Feed that per-run result count from there. For
       the last few runs (or all of them; depends on usage pattern) the data is
       is mostly a small number of minutes out of date. At the cache boundary,
       the per-run count is permanently wrong (single run partially represented
       in BMRT cache, true for probably just one of many runs). All that is
       fine, the UI does not claim real time truth in that regard. In the vast
       majority of the cases we want a ~correct result count per run only for
       the last ~10 runs, and that is provided by this approach.

    -  The result count from the BMRT cache is built as of today using only
       non-errored results.

    -  At the time of writing, per-result hardware and commit information still
       requires reaching out to other DB tables. Attribute lookups result in
       O(N) SELECT statements being issued. It makes therefore sense to cache
       the return value of this function for a small number of minutes.
    """

    # Get one result per run from DB. Expect results to be sorted in time, most
    # recent first.
    bmrs = fetch_one_result_per_n_recent_runs()

    runs_for_display: List[RunForDisplay] = []

    for bmr in bmrs:
        result_count = "n/a"
        if bmr.run_id in bmrt_cache["by_run_id"]:
            result_count = str(len(bmrt_cache["by_run_id"]))

        runs_for_display.append(
            RunForDisplay(
                run_id=bmr.run_id,
                time_for_table=bmr.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                repo_url=bmr.commit_repo_url,
                commit_message_short=bmr.ui_commit_short_msg,
                result_count=result_count,
                commit=bmr.commit,  # this may emit a DB query
                run_reason=bmr.run_reason if bmr.run_reason else "n/a",
                hardware_name=bmr.hardware.name,  # this may emit a DB query
            )
        )

    return runs_for_display


@dataclass
class RunForDisplay:
    # Note(JP). dataclass tailored for displaying per-run information in the
    # UI. Note that for VSCode support for Python variable types and
    # auto-completion in a jinja2 templates is not yet there:
    # https://github.com/microsoft/pylance-release/discussions/4090
    run_id: str
    time_for_table: str
    commit_message_short: str
    repo_url: str
    # result count is str because it may also be "n/a"
    result_count: str
    hardware_name: str
    run_reason: str
    commit: Optional[Commit]


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
