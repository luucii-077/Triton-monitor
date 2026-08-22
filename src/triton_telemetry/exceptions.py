class TritonError(Exception):
    """Base semántica de los errores del monitor."""


class ProviderTimeoutError(TritonError):
    """Un proveedor superó el tiempo de espera configurado."""


class CorruptedPayloadError(TritonError):
    """La respuesta HTTP o su contenido no cumple el contrato esperado."""


class NetworkPeeringError(TritonError):
    """La red no pudo resolver o alcanzar el proveedor."""