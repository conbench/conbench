import getpass
import os
import sys
from typing import Optional


class ConfigClass:
    APPLICATION_NAME = os.environ.get("APPLICATION_NAME", "Conbench")
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

    # When this appears to be `true` then the application initialization phase
    # executes code that _attempts_ to create all database tables. That code
    # does not error out when it finds that the database tables already exist.
    CREATE_ALL_TABLES = os.environ.get("CREATE_ALL_TABLES", "true") == "true"

    # An integer number of commits representing the max size of the rolling windows used
    # when calculating statistics like distribution mean and standard deviation. The
    # default is 100. Larger numbers will lead to more false negatives when alerting on
    # regressions, especially after large changes. We recommend leaving it as the
    # default.
    DISTRIBUTION_COMMITS = int(os.environ.get("DISTRIBUTION_COMMITS", 100))

    LOG_LEVEL_STDERR = os.environ.get("CONBENCH_LOG_LEVEL_STDERR", "INFO")
    LOG_LEVEL_FILE = None
    LOG_LEVEL_SQLALCHEMY = "WARNING"

    # Note that GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET are the legacy env vars
    # previously used for enabling OIDC SSO. Keep using these env vars for now.
    OIDC_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    OIDC_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)

    # Introduce a `Config.TESTING` boolean that application logic can use to
    # know when code is executed in the context of the test suite. This can be
    # useful for example for logging more or less detail in the context of the
    # test suite. For now use the FLASK_ENV environment variable to detect
    # this.
    TESTING = False
    if os.environ.get("FLASK_ENV") == "development":
        TESTING = True

    def __init__(self):
        self.INTENDED_BASE_URL = self._get_intended_base_url_from_env_or_exit()
        self.OIDC_ISSUER_URL = self._get_oidc_issuer_url_from_env_or_exit()

    def _get_intended_base_url_from_env_or_exit(self) -> str:
        """
        If this function returns then the output is guaranteed to start with 'http'
        and ends with a slash.

        Note: might want to do a little more URL-specific input validation via e.g.
        https://validators.readthedocs.io/en/latest/#module-validators.url


        `INTENDED_BASE_URL` is the base URL (scheme, DNS name, path prefix) that
        regular HTTP clients are expected to use for reaching the HTTP server
        exposing the app. Depends on the deployment and cannot generally be
        determined by the app itself (requires human input). Meaningful values may
        look like

        https://conbench.ursa.dev/  or  http://127.0.0.1:9000/

        This value is required to be provided by operators. That reduces code
        complexity and enhances maintainability and security. Notably, this
        simplifies code, reasoning, testing in the context of single sign-on.
        """
        ibu = os.environ.get("CONBENCH_INTENDED_BASE_URL", None)

        if ibu is None:
            sys.exit("enviroment: CONBENCH_INTENDED_BASE_URL is required but not set")

        # Strip leading and trailing whitespace.
        ibu = ibu.strip()

        if not ibu.startswith("http"):
            sys.exit(
                f"CONBENCH_INTENDED_BASE_URL must start with 'http'. Got instead:`{ibu}`"
            )

        # Require trailing slash towards tidy URL generation.
        if not ibu.endswith("/"):
            ibu += "/"

        return ibu

    def _get_oidc_issuer_url_from_env_or_exit(self) -> Optional[str]:
        """Return `None` or a string.

        If `OIDC_ISSUER_URL` is after all `None`: disable OpenID Connect (OIDC)
        single sign-on. If this is not `None` then it must be a valid OIDC issuer
        notation (that is, a URL).
        """

        oiu = os.environ.get("CONBENCH_OIDC_ISSUER_URL", None)
        if oiu is not None:
            assert oiu.startswith("http")
            # Remove all trailing slashes to make URL construction predictable.
            # ALos, the canonical form of an OIDC issuer URL does not have
            # trailing slashes.
            oiu = oiu.rstrip("/")
        else:
            # legacy config support: when CONBENCH_OIDC_ISSUER_URL is set in the
            # environment it takes precedence. If it is not set and if
            # GOOGLE_CLIENT_ID is set in the environment then set issuer to
            # "https://accounts.google.com"
            if "GOOGLE_CLIENT_ID" in os.environ:
                oiu = "https://accounts.google.com"

        # Require client ID and client secret to be set if issuer is configured.
        # Those three parameters are all required for an OIDC authorization code
        # flow.
        if oiu is not None:
            assert self.OIDC_CLIENT_ID is not None
            assert self.OIDC_CLIENT_SECRET is not None

        return oiu


Config = ConfigClass()
# for legacy code that imports via `from ..config import TestConfig`
TestConfig = Config
