"""Servicios de gestión de contraseñas.

Este módulo centraliza la lógica para hashear y verificar contraseñas usando la
biblioteca `pwdlib`.
"""

from pwdlib import PasswordHash


class PasswordService:
    """Provee utilidades para hashear y verificar contraseñas.

    La instancia mantiene una configuración recomendada de `PasswordHash` para
    asegurar parámetros adecuados de hashing.

    Attributes:
        password_hash: Instancia configurada de `PasswordHash`.
    """

    def __init__(self) -> None:
        """Inicializa el servicio con la configuración recomendada de hashing."""

        self.password_hash = PasswordHash.recommended()
    
    def hash_password(self, password: str) -> str:
        """Genera el hash de una contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash generado para almacenar de forma segura la contraseña.
        """

        return self.password_hash.hash(password)
    
    def verify_password(self, plain_password:str, hashed_password:str) -> bool:
        """Verifica si una contraseña coincide con un hash almacenado.

        Args:
            plain_password: Contraseña en texto plano a verificar.
            hashed_password: Hash previamente almacenado.

        Returns:
            `True` si la contraseña coincide con el hash, `False` en caso
            contrario.
        """

        return self.password_hash.verify(plain_password, hashed_password)
