import argparse
import asyncio
import logging

from triton_telemetry import (
    CorruptedPayloadError,
    NetworkPeeringError,
    ProviderTimeoutError,
    parse_cluster_id,
    parse_timeout,
    scan_all_providers,
    setup_triton_logging,
)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="TritonMonitor",
        description="Sistema de telemetría multicloud y observabilidad asíncrona.",
    )
    parser.add_argument(
        "providers",
        nargs="+",
        choices=["AWS", "Azure", "GCP"],
        help="Proveedores que se consultarán en paralelo.",
    )
    parser.add_argument("-c", "--cluster-id", required=True, type=parse_cluster_id)
    parser.add_argument("-t", "--timeout", type=parse_timeout, default=2.5)
    parser.add_argument(
        "-m", "--mode", choices=["nominal", "debug", "emergency"], default="nominal"
    )
    parser.add_argument("--chaos", action="store_true")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--quiet", action="store_true")
    output.add_argument("--verbose", action="store_true")
    return parser


def report_group(logger: logging.Logger, title: str, group: BaseExceptionGroup) -> None:
    logger.error(title, exc_info=(type(group), group, group.__traceback__))
    for error in group.exceptions:
        for note in getattr(error, "__notes__", []):
            logger.error("Detalle forense: %s", note)


async def run(args: argparse.Namespace, logger: logging.Logger) -> None:
    logger.info(
        "Monitoreo iniciado",
        extra={
            "cluster_id": args.cluster_id,
            "mode": args.mode,
            "providers": args.providers,
            "timeout": args.timeout,
        },
    )
    if args.chaos:
        logger.warning("Modo caos activado")

    try:
        results = await scan_all_providers(args.providers, args.timeout, args.chaos)
    except* ProviderTimeoutError as group:
        report_group(logger, "Se detectaron timeouts de proveedores", group)
    except* CorruptedPayloadError as group:
        report_group(logger, "Se detectaron respuestas HTTP o payloads inválidos", group)
    except* NetworkPeeringError as group:
        report_group(logger, "Se detectaron fallos de red o peering", group)
    else:
        for result in results:
            logger.info("Proveedor operativo", extra=result)


def main() -> None:
    args = build_cli_parser().parse_args()
    logger = setup_triton_logging()
    if args.quiet:
        logger.handlers[0].level = logging.ERROR
    elif args.verbose:
        logger.handlers[0].level = logging.DEBUG
    try:
        asyncio.run(run(args, logger))
    finally:
        logger.triton_listener.stop()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
