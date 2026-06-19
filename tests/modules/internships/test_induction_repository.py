from app.modules.internships.repositories.internship_repository import InternshipRepository


class FakeScalarResult:
    def scalar_one_or_none(self):
        return None


class FakeDb:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeScalarResult()


async def test_active_induction_query_is_deterministic_and_limited() -> None:
    db = FakeDb()
    repository = InternshipRepository(db)

    result = await repository.get_active_induction_content()

    assert result is None
    compiled = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY" in compiled
    assert "published_at DESC" in compiled
    assert "induction_content_versions.id DESC" in compiled
    assert "LIMIT 1" in compiled
