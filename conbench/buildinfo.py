import json
import logging
from dataclasses import dataclass
from typing import Optional

import dacite

log = logging.getLogger(__name__)


@dataclass
class Buildinfo:
    # Full-length git commit hash.
    commit: str
    # Name of the branch carrying the commit.
    branch_name: str
    # Example value: 2023-02-06 12:01:01Z
    build_time_rfc3339: str
    build_hostname: str
    # Version string as set by CI. Might as of today not be the same as
    # __version__ of the Conbench webapp Python package. Needs consoldidation
    # in the future.
    version_string: str


# TODO: require this, remove ambiguity (crash if file not there or in
# unexpected shape)
BUILD_INFO: Optional[Buildinfo] = None
try:
    # Try to discover additional build information at well-known path. For now,
    # do not crash the application upon: file not found, file having unexpected
    # contents, etc.
    with open("/buildinfo.json", "rb") as fh:
        data = json.loads(fh.read().decode("utf-8"))
        log.info("decoded build info JSON: %s", data)

    # `dacite.from_dict()` validates against dataclass types, rendering the
    # type info on the dataclass reliable.
    BUILD_INFO = dacite.from_dict(data_class=Buildinfo, data=data)
except Exception as exc:
    log.info("graceful degradation, could not read/parse buildinfo: %s", exc)
