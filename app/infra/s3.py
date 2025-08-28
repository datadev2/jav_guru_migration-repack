import io

from aiobotocore.session import get_session as s3_get_session

from app.config import config


class S3Client:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        self._bucket = bucket
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._client = s3_get_session()

    @property
    def client(self):
        return self._client.create_client(
            "s3",
            endpoint_url=f"https://{self._endpoint}",
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            verify=False,
        )

    async def put_object(
        self,
        file: io.BytesIO,
        filename: str,
        content_type: str = "video/mp4",
        content_disposition: str = "inline",
    ) -> dict:
        s3_client = self.client
        async with s3_client as client:
            upload = await client.put_object(
                Bucket=self._bucket,
                Key=filename,
                Body=file.getvalue(),
                ContentType=content_type,
                ContentDisposition=content_disposition,
            )
            return upload

    async def object_info(self, filename: str) -> dict:
        async with self.client as client:
            obj_info = await client.head_object(Bucket=self._bucket, Key=filename)
        return obj_info

    async def get_download_link(self, filename: str, expires_in: int = None):
        async with self._client as client:
            url = await client.generate_presigned_url(
                "get_object", Params={"Bucket": config.MINIO_BUCKET, "Key": filename}, ExpiresIn=expires_in
            )
        return url


s3 = S3Client(
    endpoint=config.S3_ENDPOINT,
    access_key=config.S3_ACCESS_KEY.get_secret_value(),
    secret_key=config.S3_SECRET_KEY.get_secret_value(),
    bucket=config.S3_BUCKET,
)
