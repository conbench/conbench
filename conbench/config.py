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


class TestConfig(Config):
    DB_NAME = os.environ.get("DB_NAME", f"{APPLICATION_NAME.lower()}_test")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{Config.DB_USERNAME}:{Config.DB_PASSWORD}"
        f"@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}"
    )
