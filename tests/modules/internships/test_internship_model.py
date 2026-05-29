from datetime import datetime

from app.modules.internships.models.internship_model import Internship


def test_upload_date_default_matches_database_timezone_naive_timestamp() -> None:
    default_value = Internship.__table__.c.upload_date.default.arg(None)

    assert isinstance(default_value, datetime)
    assert default_value.tzinfo is None


def test_internship_model_includes_supervisor_snapshot_columns() -> None:
    columns = Internship.__table__.c

    assert "supervisor_name" in columns
    assert "supervisor_profession" in columns
    assert "supervisor_position" in columns
    assert "supervisor_department" in columns
    assert "supervisor_email" in columns
    assert "supervisor_phone" in columns


def test_internship_modality_enum_matches_database_contract() -> None:
    modality_values = set(Internship.__table__.c.modality.type.enums)

    assert modality_values == {"Presencial", "Remoto", "Híbrido"}
