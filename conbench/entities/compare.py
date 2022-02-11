import flask as f

from ..entities._entity import EntitySerializer
from ..entities.commit import CommitSerializer
from ..entities.run import Run


class _Serializer(EntitySerializer):
    def _dump(self, commits):
        def _run(contender):
            baseline = contender.get_baseline_run()
            baseline_url, contender_url, compare_url = None, None, None
            baseline_timestamp, contender_timestamp = None, None

            if baseline and contender:
                compare_ids = f"{baseline.id}...{contender.id}"
                compare_url = f.url_for(
                    "api.compare-runs",
                    compare_ids=compare_ids,
                    _external=True,
                )
            if baseline:
                baseline_timestamp = baseline.timestamp.isoformat()
                baseline_url = f.url_for(
                    "api.run",
                    run_id=baseline.id,
                    _external=True,
                )
            if contender:
                contender_timestamp = contender.timestamp.isoformat()
                contender_url = f.url_for(
                    "api.run",
                    run_id=contender.id,
                    _external=True,
                )

            return {
                "baseline": {
                    "hardware_name": baseline.hardware.name if baseline else None,
                    "run": baseline_url,
                    "run_id": baseline.id if baseline else None,
                    "run_name": baseline.name if baseline else None,
                    "run_timestamp": baseline_timestamp,
                },
                "contender": {
                    "hardware_name": contender.hardware.name if contender else None,
                    "run": contender_url,
                    "run_id": contender.id if contender else None,
                    "run_name": contender.name if contender else None,
                    "run_timestamp": contender_timestamp,
                },
                "compare": compare_url,
            }

        baseline_commit, contender_commit = commits
        contender_runs = Run.all(commit_id=contender_commit.id)
        compare_shas = f"{baseline_commit.sha}...{contender_commit.sha}"
        result = {
            "commits": {
                "baseline": CommitSerializer().one.dump(baseline_commit),
                "contender": CommitSerializer().one.dump(contender_commit),
            },
            "runs": [_run(r) for r in contender_runs],
            "links": {
                "self": f.url_for(
                    "api.compare-commits", compare_shas=compare_shas, _external=True
                ),
            },
        }
        result["commits"]["baseline"].pop("links", None)
        result["commits"]["contender"].pop("links", None)
        return result


class CompareSummarySerializer:
    one = _Serializer()
    many = _Serializer(many=True)
