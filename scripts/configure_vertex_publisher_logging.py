#!/usr/bin/env python3
"""Idempotent configuration script for Vertex AI Publisher Model request-response logging to BigQuery.

This script configures Google Vertex AI / Agent Platform PublisherModelConfig for Gemini
models to enable 100% request-response logging into the dedicated BigQuery observability dataset.

Context & Exception Note (P0 AI Observability):
As of the current Terraform Google provider, there is no native resource for the v1beta1
setPublisherModelConfig API endpoint on publisher models (projects/*/locations/*/publishers/google/models/*).
This repository-owned script manages this configuration idempotently using Application Default Credentials (ADC)
or gcloud auth tokens.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("configure_vertex_publisher_logging")

DEFAULT_PROJECT = os.getenv("GCP_PROJECT_ID", "croviq-506602")
DEFAULT_LOCATION = os.getenv("VERTEXAI_LOCATION", "global")
DEFAULT_DATASET = "croviq_ai_observability"
DEFAULT_TABLE = "gemini_requests"
CANONICAL_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.5-transcribe-preview",
    "gemini-3.1-flash-tts-preview",
    "gemini-omni-1.1-flash-preview",
]


def get_access_token() -> str:
    """Retrieve OAuth2 access token via google.auth or gcloud CLI fallback."""
    token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
    if token:
        return token.strip()

    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        if credentials.token:
            return credentials.token
    except Exception as exc:
        logger.debug("google.auth token acquisition fallback: %s", exc)

    import subprocess

    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def set_publisher_model_config(
    project_id: str,
    location: str,
    model_id: str,
    dataset_id: str,
    table_id: str,
    access_token: str,
) -> dict[str, Any]:
    """Invoke setPublisherModelConfig on Vertex AI global/regional publisher model endpoint."""
    destination_uri = f"bq://{project_id}.{dataset_id}.{table_id}"
    url = (
        f"https://aiplatform.googleapis.com/v1beta1/"
        f"projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:setPublisherModelConfig"
    )

    payload = {
        "publisherModelConfig": {
            "loggingConfig": {
                "enabled": True,
                "samplingRate": 1.0,
                "bigqueryDestination": {
                    "outputUri": destination_uri,
                },
            }
        }
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": project_id,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        if exc.code == 409 and ("ALREADY_EXISTS" in err_body or "already exists" in err_body.lower()):
            logger.info("PublisherModelConfig for %s is already up-to-date (ALREADY_EXISTS).", model_id)
            return {"status": "ALREADY_CONFIGURED", "model": model_id}
        logger.error("Failed setPublisherModelConfig for %s (HTTP %d): %s", model_id, exc.code, err_body)
        raise RuntimeError(f"HTTP {exc.code} for {model_id}: {err_body}") from exc

def wait_for_operation(operation_name: str, access_token: str, project_id: str, timeout_seconds: int = 60) -> dict[str, Any]:
    """Poll the long-running operation returned by setPublisherModelConfig until done."""
    url = f"https://aiplatform.googleapis.com/v1beta1/{operation_name}"
    start = time.time()

    while time.time() - start < timeout_seconds:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": project_id,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("done", False):
                    return data
        except Exception as exc:
            logger.warning("Error checking operation %s: %s", operation_name, exc)

        time.sleep(1.0)

    raise TimeoutError(f"Operation {operation_name} did not complete within {timeout_seconds}s")


def configure_all_models(
    project_id: str = DEFAULT_PROJECT,
    location: str = DEFAULT_LOCATION,
    dataset_id: str = DEFAULT_DATASET,
    table_id: str = DEFAULT_TABLE,
    models: list[str] | None = None,
) -> dict[str, Any]:
    """Idempotently configure request/response logging across all specified models."""
    target_models = models or CANONICAL_MODELS
    token = get_access_token()
    results: dict[str, Any] = {}

    logger.info(
        "Configuring Vertex AI PublisherModelConfig for project=%s, location=%s, destination=bq://%s.%s.%s",
        project_id,
        location,
        project_id,
        dataset_id,
        table_id,
    )

    for model_id in target_models:
        logger.info("Setting PublisherModelConfig for model: %s ...", model_id)
        try:
            op_data = set_publisher_model_config(
                project_id=project_id,
                location=location,
                model_id=model_id,
                dataset_id=dataset_id,
                table_id=table_id,
                access_token=token,
            )
            op_name = op_data.get("name")
            if op_name:
                logger.info("Operation created: %s, waiting for completion...", op_name)
                final_op = wait_for_operation(op_name, token, project_id)
                results[model_id] = {
                    "status": "CONFIGURED",
                    "operation": op_name,
                    "response": final_op.get("response", {}),
                }
                logger.info("Successfully configured %s.", model_id)
            else:
                results[model_id] = {
                    "status": "CONFIGURED",
                    "response": op_data,
                }
        except Exception as exc:
            logger.error("Failed configuring %s: %s", model_id, exc)
            results[model_id] = {
                "status": "FAILED",
                "error": str(exc),
            }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Vertex AI Publisher Model BigQuery logging.")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT, help="Google Cloud Project ID")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Vertex AI location (default: global)")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET, help="BigQuery Dataset ID")
    parser.add_argument("--table-id", default=DEFAULT_TABLE, help="BigQuery Table ID")
    parser.add_argument("--models", nargs="*", default=CANONICAL_MODELS, help="List of model IDs")

    args = parser.parse_args()
    results = configure_all_models(
        project_id=args.project_id,
        location=args.location,
        dataset_id=args.dataset_id,
        table_id=args.table_id,
        models=args.models,
    )
    failed = [m for m, r in results.items() if r.get("status") not in ("CONFIGURED", "ALREADY_CONFIGURED")]
    if failed:
        logger.error("Configuration failed for models: %s", failed)
        return 1

    logger.info("All models configured successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
