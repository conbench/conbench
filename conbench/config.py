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


class TestConfig(Config):
    DB_NAME = os.environ.get("DB_NAME", f"{APPLICATION_NAME.lower()}_test")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{Config.DB_USERNAME}:{Config.DB_PASSWORD}"
        f"@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}"
    )
