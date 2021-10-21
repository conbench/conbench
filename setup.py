import pathlib
import os

import setuptools

setup_dir = os.path.abspath(os.path.dirname(__file__))

with open("README.md", "r") as readme:
    long_description = readme.read()


install_requires = [
    line.strip()
    for line in pathlib.Path(__file__)
    .parent.joinpath("requirements-cli.txt")
    .read_text()
    .splitlines()
]

# using setuptools SCM versioning
# the code below comes from pyarrow with minor changes
# In the event of not running from a git clone (e.g. from a git archive
# or a Python sdist), see if we can set the version number ourselves
default_version = '1.33.0-SNAPSHOT'
if (not os.path.exists('../.git') and
        not os.environ.get('SETUPTOOLS_SCM_PRETEND_VERSION')):
    os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = \
        default_version.replace('-SNAPSHOT', 'a0')

# See https://github.com/pypa/setuptools_scm#configuration-parameters
scm_version_write_to_prefix = os.environ.get(
    'SETUPTOOLS_SCM_VERSION_WRITE_TO_PREFIX', setup_dir)


def parse_git(root, **kwargs):
    """
    Parse function for setuptools_scm that ignores tags for non-C++
    subprojects, e.g. apache-arrow-js-XXX tags.
    """
    from setuptools_scm.git import parse
    kwargs['describe_command'] =\
        'git describe --dirty --tags --long --match "conbench-[0-9].*"'
    return parse(root, **kwargs)


def guess_next_dev_version(version):
    if version.exact:
        return version.format_with('{tag}')
    else:
        def guess_next_version(tag_version):
            return default_version.replace('-SNAPSHOT', '')
        return version.format_next_version(guess_next_version)

setuptools.setup(
    name="conbench",
    # version="1.33.0",
    use_scm_version={
        'root': os.path.dirname(setup_dir),
        'parse': parse_git,
        'write_to': os.path.join(scm_version_write_to_prefix,
                                 'conbench/_generated_version.py'),
        'version_scheme': guess_next_dev_version
    },
    # use_scm_version=True,
    description="Continuous Benchmarking (CB) Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "conbench=conbench.cli:conbench",
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
    install_requires=install_requires,
    setup_requires=['setuptools_scm']
)
