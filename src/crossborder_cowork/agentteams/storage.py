from __future__ import annotations

"""Small read-only client for the AgentTeams S3-compatible shared store.

AgentTeams workers publish task state and deliverables through its object
storage.  The Web requester only needs signed GETs; it must not mirror or
mutate the shared tree and must not invent a second task protocol.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote

import httpx


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


class AgentTeamsObjectStore:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket.strip("/")
        self.access_key = access_key
        self.secret_key = secret_key

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)

    def get(self, key: str) -> bytes | None:
        if not self.available:
            return None
        key = str(key or "").strip().lstrip("/")
        if not key or ".." in key.split("/"):
            return None
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date = now.strftime("%Y%m%d")
        region = "us-east-1"
        service = "s3"
        path = f"/{quote(self.bucket, safe='-_.~')}" + "/" + quote(key, safe="/-_.~")
        host = self.endpoint.split("://", 1)[-1].split("/", 1)[0]
        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join((
            "GET", path, "", canonical_headers, signed_headers, payload_hash,
        ))
        scope = f"{date}/{region}/{service}/aws4_request"
        string_to_sign = "\n".join((
            "AWS4-HMAC-SHA256", amz_date, scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ))
        k_date = _hmac(("AWS4" + self.secret_key).encode("utf-8"), date)
        k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
        signing_key = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        response = httpx.get(
            f"{self.endpoint}{path}",
            headers={
                "Host": host,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
                "Authorization": authorization,
            },
            timeout=15,
        )
        if response.status_code == 404:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"agentteams_storage_http_{response.status_code}: {response.text[:300]}")
        return response.content
