from datetime import datetime

from app.modules.internships.models.internship_model import Internship


def test_upload_date_default_matches_database_timezone_naive_timestamp() -> None:
    default_value = Internship.__table__.c.upload_date.default.arg(None)

    assert isinstance(default_value, datetime)
    assert default_value.tzinfo is None
