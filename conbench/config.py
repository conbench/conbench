import getpass
import os

APPLICATION_NAME = "Conbench"


class Config:
    APPLICATION_NAME = os.environ.get("APPLICATION_NAME", APPLICATION_NAME)
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", f"{APPLICATION_NAME.lower()}_prod")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_USERNAME = os.environ.get("DB_USERNAME", getpass.getuser())
    REGISTRATION_KEY = os.environ.get("REGISTRATION_KEY", "conbench")
    SECRET_KEY = os.environ.get("SECRET_KEY", "Person, woman, man, camera, TV")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    CREATE_ALL_TABLES = os.environ.get("CREATE_ALL_TABLES", "true") == "true"
    # An integer number of commits to use when calculating
    # statistics. The default is 100; larger numbers will lead to more false negatives,
    # especially after large changes. We recommend leaving it as the default. Previously
    # recorded values will not be recalculated if this value is changed. If you would
    # like to change previous values, you would need to write a migration of the data
    # to recalculate history.
    DISTRIBUTION_COMMITS = int(os.environ.get("DISTRIBUTION_COMMITS", 100))

    # The base URL (scheme, DNS name, path prefix) that regular HTTP clients
    # are expected to use for reaching the HTTP server exposing the app.
    # Depends on the deployment and cannot generally be determined by the app
    # itself (requires human input). The default value is tailored to the Flask
    # development HTTP server defaults (non-TLS, binds on 127.0.0.1, port
    # 5000). Can be adjusted via the `--host` and `--port` command line flags
    # when invoking `flask run`. Three interesting scenarios:
    # - local dev setup with default listen address: no action needed
    # - local dev setup with custom listen address: user should set meaningful
    #   value
    # - prod/staging setup: user should set meaningful value such as for
    #   example https://conbench.ursa.dev/
    #
    # Currently used for populating the 'Servers' dropdown in the
    # Swagger/OpenAPI docs website.
    INTENDED_BASE_URL = os.environ.get(
        "CONBENCH_INTENDED_BASE_URL", "http://127.0.0.1:5000/"
    )
    # Require trailing slash towards tidy URL generation.
    # Note: might want to catch bad input via e.g.
    # https://validators.readthedocs.io/en/latest/#module-validators.url
    if not INTENDED_BASE_URL.endswith("/"):
        INTENDED_BASE_URL += "/"

    LOG_LEVEL_STDERR = os.environ.get("CONBENCH_LOG_LEVEL_STDERR", "INFO")
    LOG_LEVEL_FILE = None
    LOG_LEVEL_SQLALCHEMY = "WARNING"


class TestConfig(Config):
    DB_NAME = os.environ.get("DB_NAME", f"{APPLICATION_NAME.lower()}_test")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{Config.DB_USERNAME}:{Config.DB_PASSWORD}"
        f"@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}"
    )
