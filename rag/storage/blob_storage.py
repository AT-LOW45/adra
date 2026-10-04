import os
import time
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pathlib import Path
from dotenv import load_dotenv
from exception.document_not_found_error import DocumentNotFoundError

# The .env lives at the repo root, two levels up from this file
# (rag/storage/blob_storage.py). Load it explicitly so blob creds are available
# regardless of import order or which entrypoint is running.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Kept as "patterngen-docs" through the rename to Adra: renaming the bucket makes the
# raw ADR markdown already stored in it unreachable.
BUCKET = os.getenv("BLOB_BUCKET", "patterngen-docs")

# Checked at import, matching how a missing LLM_API_KEY fails. Left unvalidated, the app
# starts happily, serves the UI, and reports an empty knowledge base — which reads as "no
# ADRs yet" rather than "storage was never configured". The truth only appears when the
# first blob call 500s, and in a browser that surfaces as a misleading CORS error.
_REQUIRED = {
    "BLOB_ENDPOINT": os.getenv("BLOB_ENDPOINT"),
    "BLOB_ACCESS_KEY": os.getenv("BLOB_ACCESS_KEY"),
    "BLOB_SECRET_KEY": os.getenv("BLOB_SECRET_KEY"),
}
_missing = [name for name, value in _REQUIRED.items() if not value]
if _missing:
    raise ValueError(
        "Blob storage is not configured: "
        + ", ".join(_missing)
        + f" not set. Adra stores every ADR in an S3-compatible bucket (currently "
        f"'{BUCKET}'); see the README for setting one up."
    )

client = boto3.client(
    "s3",
    endpoint_url=os.getenv("BLOB_ENDPOINT"),
    aws_access_key_id=os.getenv("BLOB_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("BLOB_SECRET_KEY"),
    region_name="us-east-1",
)


def _verify_bucket_reachable(attempts: int = 5, delay: float = 2.0) -> None:
    """Fail at startup if the bucket can't be reached, rather than on the first request.

    Retried because compose starts the app and MinIO together, so a few seconds of
    "connection refused" at boot is normal rather than a real misconfiguration.
    """
    for attempt in range(1, attempts + 1):
        try:
            client.head_bucket(Bucket=BUCKET)
            return
        except (BotoCoreError, ClientError) as error:
            if attempt == attempts:
                raise ValueError(
                    f"Blob storage unreachable at {os.getenv('BLOB_ENDPOINT')} "
                    f"(bucket '{BUCKET}') after {attempts} attempts: {error}. "
                    "Check the service is running and the bucket exists."
                ) from error
            time.sleep(delay)


_verify_bucket_reachable()

# Drafts are stored as opaque JSON strings under `drafts/<id>.json`, separate from
# the published (markdown) ADRs and never indexed. Each draft holds one version —
# saving the same id overwrites it.
DRAFT_PREFIX = "drafts/"


def _draft_key(draft_id: str) -> str:
    return f"{DRAFT_PREFIX}{draft_id}.json"


def save_draft_to_blob(draft_id: str, content: str) -> None:
    client.put_object(
        Bucket=BUCKET,
        Key=_draft_key(draft_id),
        Body=content.encode("utf-8"),
        ContentType="application/json",
    )


def get_draft_from_blob(draft_id: str) -> str | None:
    """The draft's JSON string, or None if it doesn't exist."""
    try:
        response = client.get_object(Bucket=BUCKET, Key=_draft_key(draft_id))
        return response["Body"].read().decode("utf-8")
    except Exception:
        return None


def delete_draft_from_blob(draft_id: str) -> None:
    client.delete_object(Bucket=BUCKET, Key=_draft_key(draft_id))


def list_drafts_from_blob() -> list[tuple[str, str]]:
    """All drafts as (draft_id, json_string) pairs."""
    response = client.list_objects_v2(Bucket=BUCKET, Prefix=DRAFT_PREFIX)
    drafts: list[tuple[str, str]] = []
    for obj in response.get("Contents", []):
        key: str = obj["Key"]
        if not key.endswith(".json"):
            continue
        draft_id = key[len(DRAFT_PREFIX) : -len(".json")]
        body = client.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")
        drafts.append((draft_id, body))
    return drafts


def upload_to_blob(content: str, source: str) -> None:
    client.put_object(
        Bucket=BUCKET,
        Key=source,
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )


def get_from_blob(source: str) -> str:
    try:
        response = client.get_object(Bucket=BUCKET, Key=source)
        return response["Body"].read().decode("utf-8")
    except:
        raise DocumentNotFoundError("no document found")


def delete_from_blob(source: str) -> None:
    client.delete_object(Bucket=BUCKET, Key=f"{source}")
