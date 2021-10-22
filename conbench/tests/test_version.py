import importlib.metadata as importlib_metadata

import conbench

__version__ = importlib_metadata.version("conbench")


def test_version():
    assert __version__ == conbench.__version__
