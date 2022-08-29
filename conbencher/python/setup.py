import pathlib

import setuptools

repo_root = pathlib.Path(__file__).parent

with open(repo_root / "README.md", "r") as readme:
    long_description = readme.read()

__version__ = ""
with open(repo_root / "conbencher" / "_version.py", "r") as f:
    exec(f.read())  # only overwrites the __version__ variable

install_requires = [
    line.strip()
    for line in pathlib.Path(__file__)
    .parent.joinpath("requirements.txt")
    .read_text()
    .splitlines()
]

setuptools.setup(
    name="conbencher",
    version=__version__,
    description="Utilities for Conbench Runs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.8",
    maintainer="Apache Arrow Developers",
    maintainer_email="dev@arrow.apache.org",
    url="https://github.com/conbench/conbencher",
    install_requires=install_requires,
)
