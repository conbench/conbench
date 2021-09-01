from ...tests.api import _fixtures
from ...tests.app import _asserts


class TestBatch(_asserts.GetEnforcer):
    url = "/batches/{}/"
    title = "Batch"
    redirect_on_unknown = False

    def _create(self, client):
        self.create_benchmark(client)
        return _fixtures.VALID_PAYLOAD["batch_id"]
