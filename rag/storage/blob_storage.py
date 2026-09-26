import os
import boto3
from pathlib import Path
from dotenv import load_dotenv
from exception.document_not_found_error import DocumentNotFoundError

# The .env lives at the repo root, two levels up from this file
# (rag/storage/blob_storage.py). Load it explicitly so blob creds are available
# regardless of import order or which entrypoint is running.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

client = boto3.client(
    "s3",
    endpoint_url=os.getenv("BLOB_ENDPOINT"),
    aws_access_key_id=os.getenv("BLOB_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("BLOB_SECRET_KEY"),
    region_name="us-east-1",
)

# Kept as "patterngen-docs" through the rename to Adra: renaming the bucket makes the
# raw ADR markdown already stored in it unreachable.
BUCKET = os.getenv("BLOB_BUCKET", "patterngen-docs")

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
