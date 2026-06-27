from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    FICA_ROLE,
    PRACTICE_MANAGER_ROLE,
    SECRETARY_ROLE,
    STUDENT_ROLE,
    SUPERADMIN_ROLE,
    SUPERVISOR_ROLE,
    STUDENT_ACCOUNT_MANAGER_ROLES,
    USER_ADMIN_ROLES,
)


def test_user_admin_policy_is_superadmin_only() -> None:
    assert USER_ADMIN_ROLES == [SUPERADMIN_ROLE]
    assert PRACTICE_MANAGER_ROLE not in USER_ADMIN_ROLES
    assert CAREER_DIRECTOR_ROLE not in USER_ADMIN_ROLES
    assert SECRETARY_ROLE not in USER_ADMIN_ROLES
    assert SUPERVISOR_ROLE not in USER_ADMIN_ROLES
    assert STUDENT_ROLE not in USER_ADMIN_ROLES
    assert FICA_ROLE not in USER_ADMIN_ROLES


def test_student_account_manager_policy_is_academic_only() -> None:
    assert STUDENT_ACCOUNT_MANAGER_ROLES == [
        PRACTICE_MANAGER_ROLE,
        CAREER_DIRECTOR_ROLE,
    ]
    assert SUPERADMIN_ROLE not in STUDENT_ACCOUNT_MANAGER_ROLES
    assert STUDENT_ROLE not in STUDENT_ACCOUNT_MANAGER_ROLES
