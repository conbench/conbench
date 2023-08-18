import pathlib

import setuptools

library_root = pathlib.Path(__file__).parent

with open(library_root / "README.md", "r") as readme:
    long_description = readme.read()

__version__ = ""
with open(library_root / "conbenchlegacy" / "_version.py", "r") as f:
    exec(f.read())  # only overwrites the __version__ variable


def parse_requirements(path: str):
    return [
        line.strip()
        for line in pathlib.Path(__file__)
        .parent.joinpath(path)
        .read_text()
        .splitlines()
    ]


requirements_cli = parse_requirements(path="requirements-cli.txt")

setuptools.setup(
    name="conbenchlegacy",
    version=__version__,
    description="Continuous Benchmarking (CB) Framework Legacy Library and CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "conbench=conbenchlegacy.cli:conbench",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.8",
    maintainer="Apache Arrow Developers",
    maintainer_email="dev@arrow.apache.org",
    url="https://github.com/conbench/conbench",
    install_requires=requirements_cli,
)
