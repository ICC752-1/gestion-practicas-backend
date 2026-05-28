from types import SimpleNamespace


def make_user(
    user_id: int = 1,
    email: str = "user@example.com",
    password_hash: str = "hashed",
    roles: list[str] | None = None,
):
    role_names = roles or ["Estudiante"]
    return SimpleNamespace(
        id=user_id,
        email=email,
        password_hash=password_hash,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role_name))
            for role_name in role_names
        ],
    )


def make_role(role_id: int = 1, name: str = "Estudiante"):
    return SimpleNamespace(id=role_id, name=name, description="")
