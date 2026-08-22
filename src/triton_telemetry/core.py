import asyncio
import json
import logging
from typing import Any

import httpx

from .exceptions import CorruptedPayloadError, NetworkPeeringError, ProviderTimeoutError

logger = logging.getLogger("triton_monitor")

PROVIDER_ENDPOINTS = {
    "AWS": "https://jsonplaceholder.typicode.com/posts/1",
    "Azure": "https://jsonplaceholder.typicode.com/posts/2",
    "GCP": "https://jsonplaceholder.typicode.com/posts/3",
}

CHAOS_ENDPOINTS = {
    "AWS": "https://httpbin.org/delay/3",
    "Azure": "https://httpbin.org/status/504",
    "GCP": "https://httpbin.org/xml",
}


async def query_provider_telemetry(
    provider: str, timeout: float, use_chaos: bool = False
) -> dict[str, Any]:
    url = CHAOS_ENDPOINTS[provider] if use_chaos else PROVIDER_ENDPOINTS[provider]
    logger.debug("Solicitud iniciada", extra={"provider": provider, "url": url})

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as error:
        mapped = ProviderTimeoutError(
            f"Timeout de {timeout:.1f}s superado en {provider}."
        )
        mapped.add_note(f"Provider_ID: {provider}")
        mapped.add_note(f"Requested_Timeout_Limit: {timeout}s")
        mapped.add_note(f"Target_Endpoint: {url}")
        raise mapped from error
    except httpx.HTTPStatusError as error:
        mapped = CorruptedPayloadError(
            f"Estatus HTTP no esperado de {provider}: {error.response.status_code}."
        )
        mapped.add_note(f"Provider_ID: {provider}")
        mapped.add_note(f"HTTP_Status_Code: {error.response.status_code}")
        mapped.add_note(f"HTTP_Method: {error.request.method}")
        mapped.add_note(f"Target_Endpoint: {url}")
        raise mapped from error
    except httpx.RequestError as error:
        mapped = NetworkPeeringError(
            f"No se pudo alcanzar el nodo de {provider}."
        )
        mapped.add_note(f"Provider_ID: {provider}")
        mapped.add_note(f"Network_Error_Type: {type(error).__name__}")
        mapped.add_note(f"Target_Endpoint: {url}")
        raise mapped from error

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        mapped = CorruptedPayloadError(
            f"El payload de {provider} no es JSON válido."
        )
        mapped.add_note(f"Provider_ID: {provider}")
        mapped.add_note(f"HTTP_Status_Code: {response.status_code}")
        raise mapped from error

    if not isinstance(payload, dict) or "id" not in payload:
        mapped = CorruptedPayloadError(
            f"El payload de {provider} no contiene el identificador esperado."
        )
        mapped.add_note(f"Provider_ID: {provider}")
        raise mapped

    logger.info(
        "Telemetría recibida",
        extra={"provider": provider, "status_code": response.status_code},
    )
    return {
        "provider": provider,
        "status": "NOMINAL",
        "latency_sec": response.elapsed.total_seconds(),
        "payload_id": payload["id"],
    }


async def _safe_query(
    provider: str, timeout: float, use_chaos: bool
) -> dict[str, Any] | None:
    try:
        return await query_provider_telemetry(provider, timeout, use_chaos)
    except Exception as error:
        logger.debug("Fallo capturado en tarea", extra={"provider": provider})
        return error


async def scan_all_providers(
    providers: list[str], timeout: float, use_chaos: bool = False
) -> list[dict[str, Any]]:
    tasks: list[asyncio.Task[dict[str, Any] | None]] = []
    async with asyncio.TaskGroup() as task_group:
        for provider in providers:
            tasks.append(
                task_group.create_task(
                    _safe_query(provider, timeout, use_chaos),
                    name=f"telemetry-{provider}",
                )
            )

    results: list[dict[str, Any]] = []
    errors: list[Exception] = []
    for task in tasks:
        outcome = task.result()
        if isinstance(outcome, Exception):
            errors.append(outcome)
        elif outcome is not None:
            results.append(outcome)

    if errors:
        raise ExceptionGroup("Fallos de telemetría detectados", errors)
    return results