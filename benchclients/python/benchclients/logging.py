import logging

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def fatal_and_log(msg: str, etype: BaseException = ValueError):
    """If an error occurs, log the message and raise an exception."""
    log.error(msg)
    raise etype(msg)
