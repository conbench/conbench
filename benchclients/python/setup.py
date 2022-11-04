import pathlib
from typing import List

import setuptools

repo_root = pathlib.Path(__file__).parent

with open(repo_root / "README.md", "r") as readme:
    long_description = readme.read()

__version__ = ""
with open(repo_root / "benchclients" / "_version.py", "r") as f:
    exec(f.read())  # only overwrites the __version__ variable


def read_requirements_file(filepath: pathlib.Path) -> List[str]:
    """Parse a requirements.txt file into a list of package requirements"""
    with open(filepath, "r") as f:
        requirements = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]
    return requirements


base_requirements = read_requirements_file(repo_root / "requirements.txt")
dev_requirements = read_requirements_file(repo_root / "requirements-dev.txt")

setuptools.setup(
    name="benchclients",
    version=__version__,
    description="Clients for the Conbench ecosystem",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: Apache Software License",
    ],
    python_requires=">=3.8",
    maintainer="Voltron Data",
    maintainer_email="conbench@voltrondata.com",
    url="https://github.com/conbench/conbench/tree/main/benchclients",
    install_requires=base_requirements,
    extras_require={"dev": dev_requirements},
)
