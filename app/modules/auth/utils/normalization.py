"""Utilidades para normalizacion y validacion de datos de usuario."""

import re


def normalize_rut(value: str) -> str:
    """Normaliza y valida un RUT chileno.

    Args:
        value: RUT en cualquier formato comun (con o sin puntos/guion).

    Returns:
        RUT normalizado en formato "12345678-9".

    Raises:
        ValueError: Si el RUT es invalido.
    """

    if not isinstance(value, str):
        raise ValueError("RUT invalido")

    cleaned = re.sub(r"[^0-9kK]", "", value)

    if len(cleaned) < 2:
        raise ValueError("RUT invalido")

    number = cleaned[:-1]
    verifier = cleaned[-1].upper()

    if not number.isdigit():
        raise ValueError("RUT invalido")

    number = number.lstrip("0")

    if not number:
        raise ValueError("RUT invalido")

    expected = _calculate_rut_verifier(number)
    if verifier != expected:
        raise ValueError("RUT invalido")

    return f"{number}-{verifier}"


def normalize_phone(value: str) -> str:
    """Normaliza y valida un telefono.

    Args:
        value: Telefono en formato libre.

    Returns:
        Telefono normalizado en formato E.164 (ej: +56912345678).

    Raises:
        ValueError: Si el telefono es invalido.
    """

    if not isinstance(value, str):
        raise ValueError("Telefono invalido")

    raw = value.strip()

    if not raw:
        raise ValueError("Telefono invalido")

    digits = re.sub(r"\D", "", raw)

    if not digits:
        raise ValueError("Telefono invalido")

    if raw.startswith("+"):
        if len(digits) < 8 or len(digits) > 15:
            raise ValueError("Telefono invalido")
        return f"+{digits}"

    if digits.startswith("56"):
        if len(digits) != 11:
            raise ValueError("Telefono invalido")
        return f"+{digits}"

    if len(digits) == 9:
        return f"+56{digits}"

    raise ValueError("Telefono invalido")


def _calculate_rut_verifier(number: str) -> str:
    total = 0
    multiplier = 2

    for digit in reversed(number):
        total += int(digit) * multiplier
        multiplier += 1
        if multiplier > 7:
            multiplier = 2

    remainder = 11 - (total % 11)

    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)
