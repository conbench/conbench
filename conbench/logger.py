"""
Set up Python's logging infrastructure for the web application.

Acquire root logger instance and populate it with handlers, applying a certain
log format. This takes effect for Conbench code as well as integrated
libraries, such as SQLAlchemy

A package or module within Conbench should obtain and use a logger instance in
the 'conbench' sub-tree of the logging namespace hierarchy, via e.g.

    log = logging.getLogger('conbench.xxx')
"""


import logging
import logging.handlers


def setup(
    level_stderr="ERROR",
    level_file="DEBUG",
    logfilepath="conbench.log",
    level_sqlalchemy="WARNING",
):
    """Set up root logger for the Conbench application.

    Args:
        level_stderr: `None` or a valid log level string.
        level_file: `None` or a valid log level string.
        logfilepath: Path to where a log file should be opened
            in append mode. Takes effect only when `level_file`
            defines a logging level.

    Valid log level strings:

        'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    Cf. https://docs.python.org/3/library/logging.html#levels

    Setting both levels to `None` will mute the root logger.
    """

    # Reset root logger configuration: remove existing handlers and don't
    # filter on logger level, but on handler level (pass all LogRecords
    # to attached handlers).
    rootlog = logging.getLogger()
    rootlog.handlers = []
    rootlog.setLevel(0)

    # Define formatter, to be applied to all handlers below.
    # Can use %(threadName)s when using more than one thread per process.
    logfmt = (
        "[%(asctime)s.%(msecs)03d] [%(process)d] "
        "[%(name)s] %(levelname)s: %(message)s"
    )
    datefmt = "%y%m%d-%H:%M:%S"
    formatter = logging.Formatter(fmt=logfmt, datefmt=datefmt)

    # Set up handlers.
    handlers = []
    if level_stderr:
        level = getattr(logging, level_stderr)
        h = logging.StreamHandler()
        h.setLevel(level)
        handlers.append(h)

    if level_file:
        level = getattr(logging, level_file)
        h = logging.handlers.RotatingFileHandler(
            filename=logfilepath,
            mode="a",
            maxBytes=5 * 1024 * 1024,
            backupCount=50,
            encoding="utf-8",
            delay=False,
        )
        h.setLevel(level)
        handlers.append(h)

    # For newly defined handlers: set formatter, attach to root logger.
    for h in handlers:
        h.setFormatter(formatter)
        rootlog.addHandler(h)

    if not handlers:
        # Mute root logger (prevent logging.lastResort from taking effect).
        rootlog.addHandler(logging.NullHandler())

    sa_logger = logging.getLogger("sqlalchemy.engine")
    sa_logger.setLevel(getattr(logging, level_sqlalchemy))

    # Do not show log msgs like
    # [urllib3.connectionpool] DEBUG: Starting new HTTP connection (1): ....
    logging.getLogger("urllib3.connectionpool").setLevel("INFO")
