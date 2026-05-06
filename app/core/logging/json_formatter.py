"""Define utilidades auxiliares para el logging estructurado y la salida en consola.

Este modulo se usa desde «logging_config.json» para registrar componentes
personalizados del sistema de logging. Su responsabilidad principal es:

- convertir registros de Python en lineas JSON para el handler de archivo
- separar los niveles de severidad que deben salir por «stdout» y «stderr»

Se utiliza cuando la configuracion de logging necesita un formato estructurado
para archivos y una salida de consola dividida entre mensajes informativos y
mensajes de advertencia o error.
"""

import datetime as dt
import json
import logging


# --- Formatter JSON estructurado ---
# Define el formatter que convierte cada LogRecord en una linea JSON
# para su escritura en archivos o consumo estructurado.
class JSONFormatter(logging.Formatter):
    """Convierte cada registro de logging en una sola linea JSON.

    Que hace:
    - Toma un «LogRecord» generado por el sistema de logging.
    - Extrae la informacion relevante del registro.
    - Devuelve un objeto JSON serializado en una sola linea.

    Por que existe:
    - Permite guardar logs estructurados en archivo para que sean mas faciles
      de leer, procesar y analizar despues.
    - Entra en accion cada vez que un registro debe escribirse en el destino
      configurado con este formatter.

    Como funciona:
    - Construye primero un payload intermedio con los campos del registro.
    - Luego serializa ese payload a JSON en una sola cadena.
    """

    def __init__(self, fmt_keys: dict[str, str] | None = None) -> None:
        """Inicializa el formatter con un mapeo opcional de claves de salida.

        - Recibe un diccionario que relaciona nombres de salida con atributos
          disponibles en «LogRecord».
        - Si se recibe «fmt_keys», lo guarda para usarlo al construir el
          payload; si no, usa un diccionario vacio.
        """
        super().__init__()
        self.fmt_keys = fmt_keys or {}

    def format(self, record: logging.LogRecord) -> str:
        """Serializa un registro de logging como una cadena JSON.

        - Genera un diccionario con la informacion del registro.
        - Convierte ese diccionario en una cadena JSON.
        - Este es el punto de integracion que espera el sistema de logging de
          Python para transformar un registro antes de escribirlo.
        - Delega la construccion del payload en «_build_payload()» y luego
          usa «json.dumps» para serializarlo.
        """
        payload = self._build_payload(record)
        return json.dumps(payload, default=str, ensure_ascii=False)

    def _build_payload(self, record: logging.LogRecord) -> dict:
        """Construye el contenido estructurado que sera serializado a JSON.

        Que hace:
        - Reune los campos base del registro, como mensaje y timestamp.
        - Agrega informacion de excepcion o stack trace cuando existe.
        - Incorpora las claves adicionales definidas en «fmt_keys».

        Por que existe:
        - Separa la logica de composicion del payload de la serializacion final,
          lo que hace el formatter mas claro y facil de mantener.

        Como funciona:
        - Primero crea un conjunto minimo de campos base.
        - Luego revisa si el registro incluye excepciones o stack info.
        - Despues arma el payload final combinando el mapeo configurado con los
          campos base ya calculados.
        """
        base_fields: dict[str, object] = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }

        if record.exc_info is not None:
            base_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            base_fields["stack_info"] = self.formatStack(record.stack_info)

        payload: dict[str, object] = {}

        for out_key, record_attr in self.fmt_keys.items():
            if record_attr in base_fields:
                payload[out_key] = base_fields[record_attr]
            else:
                payload[out_key] = getattr(record, record_attr, None)

        payload.update(base_fields)
        return payload


# --- Filtros por nivel para consola ---
# Separa los registros segun su severidad para dirigirlos a stdout o stderr
# de acuerdo con la configuracion del sistema de logging.
class BelowWarningFilter(logging.Filter):
    """Permite solo registros con severidad menor a «WARNING».

    Que hace:
    - Deja pasar registros «DEBUG» e «INFO».
    - Bloquea «WARNING», «ERROR» y «CRITICAL».

    Por que existe:
    - Ayuda a separar la salida informativa normal de los mensajes de error en
      la configuracion de consola.

    Donde y cuando se usa:
    - Se usa en el handler que escribe hacia «stdout».
    - Se evalua cada vez que un registro intenta pasar por ese handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Indica si el registro debe pasar al handler de salida normal.

        Que hace:
        - Comprueba si el nivel del registro es menor a «WARNING».

        Por que existe:
        - Define de forma explicita que niveles se consideran salida normal.

        Como funciona:
        - Devuelve «True» cuando «record.levelno» es menor a «WARNING».
        """
        return record.levelno < logging.WARNING


class WarningAndAboveFilter(logging.Filter):
    """Permite solo registros con severidad «WARNING» o superior.

    Que hace:
    - Deja pasar «WARNING», «ERROR» y «CRITICAL».
    - Bloquea los niveles informativos inferiores.

    Por que existe:
    - Ayuda a dirigir advertencias y errores a un stream distinto del usado
      para la salida normal de consola.

    Donde y cuando se usa:
    - Se usa en el handler que escribe hacia «stderr».
    - Se evalua cada vez que un registro intenta pasar por ese handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Indica si el registro debe pasar al handler de errores.

        Que hace:
        - Comprueba si el nivel del registro es «WARNING» o superior.

        Por que existe:
        - Define de forma explicita que niveles deben considerarse salida de
          advertencia o error.

        Como funciona:
        - Devuelve «True» cuando «record.levelno» es mayor o igual a
          «WARNING».
        """
        return record.levelno >= logging.WARNING


class ErrorAndAboveFilter(logging.Filter):
    """Permite solo registros con severidad «ERROR» o superior.

    Que hace:
    - Deja pasar «ERROR» y «CRITICAL».
    - Bloquea «DEBUG», «INFO» y «WARNING».

    Por que existe:
    - Permite escribir en un archivo separado solo los errores reales de la
      aplicacion, sin mezclar advertencias que pueden ser mas frecuentes.

    Donde y cuando se usa:
    - Se usa en el handler de archivo dedicado a errores.
    - Se evalua cada vez que un registro intenta escribirse en ese archivo.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Indica si el registro debe pasar al archivo exclusivo de errores.

        Que hace:
        - Comprueba si el nivel del registro es «ERROR» o superior.

        Por que existe:
        - Define de forma explicita que eventos deben considerarse errores
          relevantes para su almacenamiento separado.

        Como funciona:
        - Devuelve «True» cuando «record.levelno» es mayor o igual a
          «ERROR».
        """
        return record.levelno >= logging.ERROR
