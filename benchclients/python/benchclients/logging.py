import logging

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


def fatal_and_log(msg: str, etype: BaseException = ValueError):
    """If an error occurs, log the message and raise an exception."""
    log.error(msg)
    raise etype(msg)
