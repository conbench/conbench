import importlib.metadata as importlib_metadata

import conbench

__version__ = importlib_metadata.version("conbench")


# Note(JP): it's a little tough to understand what this test is testing.
# Maybe we should test if the /api/ping endpoint emits the expected version.
def test_version():
    assert __version__ == conbench.__version__
