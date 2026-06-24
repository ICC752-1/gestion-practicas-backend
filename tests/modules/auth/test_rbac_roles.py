from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    FICA_ROLE,
    PRACTICE_MANAGER_ROLE,
    SECRETARY_ROLE,
    STUDENT_ROLE,
    SUPERADMIN_ROLE,
    SUPERVISOR_ROLE,
    SYSTEM_ROLE_NAMES,
    USER_ADMIN_ROLES,
)


def test_system_roles_include_fica_and_superadmin() -> None:
    assert SYSTEM_ROLE_NAMES == (
        STUDENT_ROLE,
        SUPERVISOR_ROLE,
        PRACTICE_MANAGER_ROLE,
        CAREER_DIRECTOR_ROLE,
        SECRETARY_ROLE,
        FICA_ROLE,
        SUPERADMIN_ROLE,
    )


def test_user_admin_policy_is_superadmin_only() -> None:
    assert USER_ADMIN_ROLES == [SUPERADMIN_ROLE]
    assert PRACTICE_MANAGER_ROLE not in USER_ADMIN_ROLES
    assert CAREER_DIRECTOR_ROLE not in USER_ADMIN_ROLES
    assert SECRETARY_ROLE not in USER_ADMIN_ROLES
    assert SUPERVISOR_ROLE not in USER_ADMIN_ROLES
    assert STUDENT_ROLE not in USER_ADMIN_ROLES
    assert FICA_ROLE not in USER_ADMIN_ROLES
