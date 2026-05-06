"""Centraliza la configuracion e inicializacion del logging de la aplicacion."""

import json
import logging
import logging.config
from pathlib import Path

from app.core.config import config


# --- Punto de entrada publico ---
# Inicializa el sistema de logging y coordina la carga de configuracion,
# junto con los ajustes dinamicos aplicados sobre los handlers configurados.
def setup_logging() -> None:
    """Inicializa el sistema de logging de la aplicacion.

    Que hace:
    - Carga la configuracion base desde «logging_config.json».
    - Aplica los valores dinamicos definidos en las variables de entorno.
    - Registra la configuracion final en el sistema de logging de Python.

    Por que existe:
    - Centraliza en un solo punto el arranque del logging para evitar
      configuraciones dispersas o repetidas.

    Como funciona:
    - Primero comprueba si ya existen los handlers propios del proyecto.
    - Luego carga el archivo base, resuelve las rutas de los archivos de logs,
      aplica los overrides y activa los handlers configurados.
    """
    if _is_logging_already_configured():
        return

    logging_configuration_path = _get_logging_config_path()
    logging_configuration_dict = _load_logging_configuration(logging_configuration_path)
    log_file_path = _build_log_file_path(config.LOG_FILE_NAME)
    error_log_file_path = _build_log_file_path(config.LOG_ERROR_FILE_NAME)

    _apply_runtime_overrides(
        logging_configuration_dict,
        log_file_path,
        error_log_file_path,
    )
    logging.config.dictConfig(logging_configuration_dict)


# --- Rutas y carga de configuracion ---
# Reune las funciones que localizan la configuracion base del logging
# y resuelven la ruta donde deben guardarse los archivos de log.
def _get_logging_config_path() -> Path:
    """Devuelve la ruta del archivo base de configuracion de logging.

    - Ubica «logging_config.json» junto a este modulo.
    """
    return Path(__file__).with_name("logging_config.json")


def _load_logging_configuration(logging_configuration_path: Path) -> dict:
    """Carga y devuelve la configuracion base de logging desde un archivo JSON.

    - Lee el contenido del archivo indicado.
    - Lo convierte a un diccionario compatible con «dictConfig».
    - Separa la lectura del archivo de la logica principal de inicializacion.
    """
    with logging_configuration_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _build_log_file_path(file_name: str) -> Path:
    """Construye la ruta absoluta de un archivo de logs.

    - Crea el directorio de logs si todavia no existe.
    - Devuelve la ruta completa del archivo solicitado.
    - Toma «LOG_DIR» desde la configuracion.
    - Lo resuelve como ruta absoluta a partir del directorio de trabajo actual.
    - Combina ese directorio con el nombre de archivo recibido.
    """
    logs_dir = Path(config.LOG_DIR).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / file_name


# --- Overrides en tiempo de ejecucion ---
# Agrupa los ajustes dinamicos del logging.
# Aqui se aplican los valores definidos por variables de entorno, como nivel,
# directorio, nombre del archivo y parametros de rotacion.
def _apply_runtime_overrides(
    logging_configuration_dict: dict,
    log_file_path: Path,
    error_log_file_path: Path,
) -> None:
    """Aplica sobre la configuracion base los valores dinamicos del entorno.

    Que hace:
    - Ajusta el nivel global del logger raiz.
    - Define la ruta final del archivo general y del archivo de errores.
    - Configura los parametros de rotacion de ambos handlers de archivo.

    Por que existe:
    - Permite reutilizar un archivo JSON base y adaptar sus valores segun el
      entorno donde se ejecuta la aplicacion.

    Como funciona:
    - Modifica en memoria el diccionario cargado desde JSON antes de pasarlo a
      «logging.config.dictConfig».
    """
    logging_configuration_dict["root"]["level"] = config.LOG_LEVEL.upper()

    file_handler_config = logging_configuration_dict["handlers"]["file"]
    error_file_handler_config = logging_configuration_dict["handlers"]["error_file"]

    file_handler_config["filename"] = str(log_file_path)
    file_handler_config["maxBytes"] = int(config.LOG_MAX_BYTES)
    file_handler_config["backupCount"] = int(config.LOG_BACKUP_COUNT)

    error_file_handler_config["filename"] = str(error_log_file_path)
    error_file_handler_config["maxBytes"] = int(config.LOG_MAX_BYTES)
    error_file_handler_config["backupCount"] = int(config.LOG_BACKUP_COUNT)


# --- Estado de la configuracion activa ---
# Reune helpers que permiten detectar si el logging propio del proyecto ya fue
# aplicado, sin depender de handlers ajenos registrados por otras herramientas.
def _is_logging_already_configured() -> bool:
    """Indica si el logging propio del proyecto ya fue configurado.

    Que hace:
    - Revisa los handlers actuales del logger raiz.
    - Comprueba si ya existe el archivo general o el archivo de errores propios
      de esta configuracion.

    Por que existe:
    - Evita volver a inicializar el logging y duplicar los handlers del
      proyecto cuando la configuracion ya fue aplicada.

    Como funciona:
    - Construye las rutas esperadas para los archivos de log del proyecto.
    - Recorre los handlers actuales del logger raiz y compara sus atributos
      «baseFilename» con las rutas esperadas.
    """
    root_logger = logging.getLogger()
    expected_log_file_path = str(_build_log_file_path(config.LOG_FILE_NAME))
    expected_error_log_file_path = str(_build_log_file_path(config.LOG_ERROR_FILE_NAME))

    for handler in root_logger.handlers:
        base_file_name = getattr(handler, "baseFilename", None)
        if base_file_name in {expected_log_file_path, expected_error_log_file_path}:
            return True

    return False
