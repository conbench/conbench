from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select

from ..db import Session
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from ..app.benchmarks import RunMixin
from ..config import Config
from ..entities.run import Run


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
        # Following
        # https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities
        runs = Session.scalars(
            select(Run).order_by(Run.timestamp.desc()).limit(1000)
        ).all()

        # Note(JP): group runs by associated commit.repository value Note that
        # consistency between benchmark results in the run is currently not
        # granted: https://github.com/conbench/conbench/issues/864

        repo_runs_map = defaultdict(list)

        for r in runs:
            rd = RunForDisplay(
                ctime_for_table=r.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                commit_message_short=short_commit_msg(r.commit.message),
                run=r,
            )
            repo_runs_map[r.commit.repository].append(rd)

        return self.page(repo_runs_map)


@dataclass
class RunForDisplay:
    ctime_for_table: str
    commit_message_short: str
    # Also expose the raw Run object
    run: Run
    # commit_url: Optional[str]


def short_commit_msg(msg: str):
    """
    Substitute multiple whitespace characters with a single space. Overall,
    truncate at maxlen.

    This may return an empty string.
    """
    result = " ".join(msg.split())

    maxlen = 200

    if len(result) > maxlen:
        result = result[:maxlen] + "..."

    return result


view = Index.as_view("index")
rule("/", view_func=view, methods=["GET"])
rule("/index/", view_func=view, methods=["GET"])
