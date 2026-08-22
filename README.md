# Triton-monitor
Programa de línea de comandos que simula un sistema de monitoreo de servidores en la nube (AWS, Azure y GCP). Consulta a los tres proveedores al mismo tiempo y registra todo en un archivo de log en formato JSON.

## Requisitos

- Python 3.11 o superior.
- Conexión a internet (consulta servicios públicos).

## Instalación

```bash
git clone https://github.com/TU-USUARIO/TU-REPO.git
cd TU-REPO
python -m pip install -r requirements.txt
```

## Cómo usarlo

**Modo normal** (todo funciona bien):

```bash
python run.py AWS Azure GCP --cluster-id cluster-us-east-01 --timeout 2.5
```

**Modo caos** (para ver cómo maneja errores reales):

```bash
python run.py AWS Azure GCP --cluster-id cluster-us-east-01 --timeout 1.0 --chaos --mode emergency
```

### Opciones

| Opción | Qué hace |
|---|---|
| `AWS Azure GCP` | Proveedores a consultar (obligatorio, al menos uno) |
| `--cluster-id` | Identificador del cluster, formato `cluster-pais-zona-numero` (obligatorio) |
| `--timeout` | Tiempo máximo de espera en segundos, entre 0.1 y 5.0 (por defecto: 2.5) |
| `--mode` | Modo de operación: `nominal`, `debug` o `emergency` (por defecto: `nominal`) |
| `--chaos` | Activa endpoints que fallan a propósito |
| `--quiet` | Muestra solo errores en consola |
| `--verbose` | Muestra información detallada en consola |

`--quiet` y `--verbose` no se pueden usar juntos.

## Qué pasa al ejecutarlo

1. El programa consulta a cada proveedor en paralelo (al mismo tiempo).
2. Muestra en la consola el resultado de cada proveedor.
3. Guarda todo en `triton_services.log` en formato JSON, con detalles como:
   - Fecha y hora exacta (en UTC).
   - Nivel del mensaje (INFO, WARNING, ERROR).
   - Proveedor consultado.
   - Si hubo errores, un árbol completo de excepciones con notas detalladas.
4. Cuando el archivo de log supera los 2 MB, rota solo y el anterior se comprime en `.gz`.

## Estructura del proyecto

```
project/
├── run.py                          ← Punto de entrada (ejecutar este archivo)
├── requirements.txt                ← Dependencias (httpx)
├── README.md                        ← Este archivo
└── src/
    ├── app_operator.py             ← Lógica principal: lee argumentos y ejecuta todo
    └── triton_telemetry/           ← Paquete con la lógica interna
        ├── __init__.py             ← Conecta todo lo que usa app_operator
        ├── core.py                 ← Consulta a los proveedores en paralelo
        ├── exceptions.py           ← Tipos de errores personalizados
        ├── logging_engine.py       ← Sistema de logs en JSON con rotación y gzip
        └── sanitizer.py            ← Validación de argumentos (cluster-id, timeout)
```

## Ejemplos de salida

### Modo normal (consola):

```
2026-08-22 01:20:00 [INFO] Monitoreo iniciado
2026-08-22 01:20:01 [INFO] Telemetría recibida
2026-08-22 01:20:01 [INFO] Proveedor operativo
```

### Modo caos (consola):

```
2026-08-22 01:20:00 [INFO] Monitoreo iniciado
2026-08-22 01:20:00 [WARNING] Modo caos activado
2026-08-22 01:20:01 [ERROR] Se detectaron timeouts de proveedores
2026-08-22 01:20:01 [ERROR] Detalle forense: Provider_ID: AWS
2026-08-22 01:20:01 [ERROR] Detalle forense: Requested_Timeout_Limit: 1.0s
```

## Conceptos que demuestra este proyecto

- **Programación asíncrona**: varias consultas en paralelo con `asyncio.TaskGroup`.
- **Manejo de errores**: excepciones personalizadas con notas detalladas usando `add_note()`.
- **Logging profesional**: registros en JSON con rotación automática y compresión gzip.
- **Validación de entrada**: argumentos verificados con expresiones regulares y rangos.

