import io
from minio import Minio
from minio.error import S3Error
from app.config import settings

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        try:
            if not _client.bucket_exists(settings.minio_bucket):
                _client.make_bucket(settings.minio_bucket)
        except S3Error:
            pass
    return _client


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_minio()
    client.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return key


def upload_file(key: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    client = get_minio()
    client.fput_object(settings.minio_bucket, key, file_path, content_type=content_type)
    return key


def download_bytes(key: str) -> bytes:
    client = get_minio()
    resp = client.get_object(settings.minio_bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def get_presigned_url(key: str, expires_hours: int = 1) -> str:
    from datetime import timedelta
    client = get_minio()
    return client.presigned_get_object(settings.minio_bucket, key, expires=timedelta(hours=expires_hours))
