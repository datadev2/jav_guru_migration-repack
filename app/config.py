from pydantic import Field, MongoDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    MODE: str = Field(default="DEV")

    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_NAME: str

    S3_ENDPOINT: str
    S3_ACCESS_KEY: SecretStr
    S3_SECRET_KEY: SecretStr
    S3_BUCKET: str
    S3_FOLDER: str

    REDIS_DSN: RedisDsn

    CHUNK: int = Field(default=4096)

    DRIVER: str
    AD_BLOCK: str

    SITE_NAME: str

    G_SPREADSHEET_ID: str
    G_SPREADSHEET_TAB: str = "Main"
    G_SPREADSHEET_CREDS: str

    @property
    def database_dsn(self) -> MongoDsn:
        dsn = MongoDsn.build(
            scheme="mongodb",
            host=self.DB_HOST,
            port=27017,
            username=self.DB_USER,
            password=self.DB_PASS,
        )
        return dsn


config = Config()
