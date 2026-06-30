from datetime import datetime
from types import SimpleNamespace

import pytest
from docx import Document as WordDocument
from fastapi import HTTPException

from app.modules.presentation_letters.schemas.presentation_letter_schema import (
    PresentationLetterGenerateRequest,
    PresentationLetterTemplateUpdateRequest,
)
from app.modules.presentation_letters.services.presentation_letter_service import (
    PresentationLetterService,
)


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int, *roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email=f"user{user_id}@ufrontera.cl",
        first_name="Nombre",
        last_name="Apellido",
        rut=f"1234567{user_id % 10}-{user_id % 10}",
        cod_degree=f"INF-{user_id:03d}",
        admission_year=2020,
        roles=[_role(role_name) for role_name in roles],
        is_active=True,
    )


def _template(practice_type: str = "Práctica de Estudio I") -> SimpleNamespace:
    is_controlled = practice_type == "Práctica Controlada"
    suffix = "II" if practice_type.endswith("II") else "I"
    practice_label = "Controlada" if is_controlled else f"de Estudios {suffix}"
    base_intro = (
        "Reciba un cordial saludo de parte de la Dirección de la Carrera de "
        "Ingeniería Civil Informática de la Universidad de La Frontera, una "
        "institución comprometida con la formación de profesionales capacitados "
        "para enfrentar los retos del mundo laboral actual."
    )
    student_presentation = (
        "Por medio de la presente, nos dirigimos a usted con el propósito de "
        "presentar a {{student_name}} Número de Matrícula: {{student_identifier}}, "
        "quien es estudiante regular de nuestra carrera y quien cumple todos los "
        f"requisitos para realizar su Práctica {practice_label} en una "
        "organización de reconocido prestigio como la suya."
    )
    practice_description = (
        f"La Práctica {practice_label} permite a los/as estudiantes aplicar "
        "los conocimientos adquiridos en el aula en un entorno real, fortaleciendo "
        "sus competencias mientras contribuyen al cumplimiento de los objetivos "
        "de las empresas y organizaciones que los reciben."
    )
    outcomes = {
        "I": [
            "Desarrollar la capacidad de interacción con las personas que hacen vida en la organización con la finalidad de comunicarse efectivamente y lograr un desempeño laboral acorde a lo esperado.",
            "Reconocer las estructuras organizacionales y su funcionamiento con la finalidad de ajustarse a los procedimientos de la unidad donde realiza la práctica.",
            "Reconocer las diferentes etapas de los procesos, así como sus implicancias técnicas, económicas, de gestión e impacto social, medioambiental y cultural que le permiten alinearse al quehacer de la organización desde su especialidad.",
            "Mantener una conducta responsable en prevención de riesgos y cuidado del medio ambiente en el ámbito de su desempeño práctico en modalidad presencial o virtual.",
            "Realizar actividades donde demuestra su formación académica básica y una conducta éticamente adecuada durante su permanencia en la organización.",
        ],
        "II": [
            "Utilizar un lenguaje técnico y apropiado que le permita comunicarse efectivamente con las personas que hacen vida en la organización con la finalidad de asumir el rol asignado para contribuir con el desempeño del equipo de trabajo.",
            "Comprender las estructuras organizacionales y su funcionamiento con la finalidad de ajustarse a los procedimientos de la unidad donde realiza la práctica.",
            "Aplicar los conocimientos de la especialidad para identificar problemas específicos de la organización y proponer soluciones a los mismos, considerando aspectos económicos, técnicos, de gestión y su impacto social, medioambiental y cultural.",
            "Mantener una conducta responsable en prevención de riesgos y cuidado del entorno en el ámbito de su desempeño práctico en modalidad presencial o virtual, considerando los aspectos normativos y reglamentarios que regulan la materia.",
            "Realizar actividades donde demuestra su formación profesional y una conducta éticamente adecuada durante su permanencia en la organización.",
        ],
    }
    return SimpleNamespace(
        id=3 if is_controlled else (1 if suffix == "I" else 2),
        practice_type=practice_type,
        title="Carta de Presentación",
        subtitle=f"Estudiante en Práctica {practice_label}",
        base_intro=base_intro,
        student_presentation_template=student_presentation,
        practice_description=practice_description,
        minimum_hours=168,
        minimum_hours_clause=(
            "Es importante destacar que la duración mínima de la "
            "{{practice_type}} es de {{minimum_hours}} horas cronológicas, y que una vez "
            "completada con éxito el/la estudiante debe ser capaz de evidenciar "
            "los siguientes aprendizajes:"
        ),
        learning_outcomes=outcomes[suffix],
        insurance_clause=(
            "Por último, le informamos que durante el periodo de práctica el/la "
            "estudiante se encuentra protegido/a ante eventuales accidentes con "
            "el seguro escolar, el cual se encuentra al alero del artículo 3° de "
            "la Ley 16.744, según DS N°313 Ministerio del Trabajo y Previsión Social."
        ),
        closing_text=(
            "Agradeciendo de antemano su atención y colaboración, quedamos "
            "atentos a sus comentarios."
        ),
        signature_name="Claudio Andrés Navarro Cruces",
        signature_role="Director de carrera",
        signature_institution="Universidad de La Frontera",
        is_active=True,
        created_by=None,
        updated_by=None,
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        updated_at=datetime(2026, 6, 1, 10, 0, 0),
    )


def _letter(
    letter_id: int = 1,
    *,
    student_id: int = 10,
    practice_type: str = "Práctica de Estudio I",
    file_path: str = "10/practica-i/carta.pdf",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=letter_id,
        student_id=student_id,
        practice_type=practice_type,
        template_id=1,
        generated_file_name="carta.pdf",
        generated_file_path=file_path,
        recipient_email=f"user{student_id}@ufrontera.cl",
        sent_at=None,
        downloaded_at=None,
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        updated_at=datetime(2026, 6, 1, 10, 0, 0),
        student=_user(student_id, "Estudiante"),
        template=_template(practice_type),
    )


def _template_payload() -> PresentationLetterTemplateUpdateRequest:
    return PresentationLetterTemplateUpdateRequest(
        title="Carta de Presentación",
        subtitle="Estudiante en Práctica de Estudios I",
        base_intro="Intro {{student_name}}",
        student_presentation_template="Estudiante {{student_identifier}}",
        practice_description="Descripción editable",
        minimum_hours=168,
        minimum_hours_clause=(
            "La duración requerida es de {{minimum_hours}} horas cronológicas."
        ),
        learning_outcomes=["Aprendizaje actualizado"],
        insurance_clause="Seguro escolar",
        closing_text="Cierre",
        signature_name="Claudio Andrés Navarro Cruces",
        signature_role="Director de carrera",
        signature_institution="Universidad de La Frontera",
    )


class FakePresentationLetterRepository:
    def __init__(self) -> None:
        self.templates = {
            "Práctica de Estudio I": _template("Práctica de Estudio I"),
            "Práctica de Estudio II": _template("Práctica de Estudio II"),
            "Práctica Controlada": _template("Práctica Controlada"),
        }
        self.letters: dict[int, SimpleNamespace] = {}
        self.saved_template = None
        self.saved_letter = None

    async def list_templates(self):
        return list(self.templates.values())

    async def get_active_template(self, practice_type: str):
        return self.templates.get(practice_type)

    async def save_template(self, template):
        if not getattr(template, "id", None):
            template.id = 100
        self.templates[template.practice_type] = template
        self.saved_template = template
        return template

    async def create_letter(self, letter):
        letter.id = 200
        letter.student = _user(letter.student_id, "Estudiante")
        letter.template = self.templates[letter.practice_type]
        self.letters[letter.id] = letter
        return letter

    async def save_letter(self, letter):
        self.saved_letter = letter
        self.letters[letter.id] = letter
        return letter

    async def get_letter_by_id(self, letter_id: int):
        return self.letters.get(letter_id)

    async def list_letters_for_student(self, student_id: int):
        return [
            letter
            for letter in self.letters.values()
            if letter.student_id == student_id
        ]


class FakeNotificationService:
    def __init__(self) -> None:
        self.notifications = []

    async def create_and_dispatch(self, notification):
        self.notifications.append(notification)
        notification.id = len(self.notifications)
        return notification


def _config(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(PRESENTATION_LETTER_STORAGE_DIR=str(tmp_path))


def _service(
    tmp_path,
    repository: FakePresentationLetterRepository | None = None,
    notifications: FakeNotificationService | None = None,
) -> PresentationLetterService:
    return PresentationLetterService(
        repository=repository or FakePresentationLetterRepository(),
        app_config=_config(tmp_path),
        notification_service=notifications,
    )


def _patch_pdf_conversion(monkeypatch, content: bytes = b"%PDF-1.7\nfrom-docx") -> None:
    def fake_convert(self, docx_path, output_dir):  # noqa: ANN001
        assert docx_path.is_file()
        assert docx_path.suffix == ".docx"
        assert output_dir.is_dir()
        return content

    monkeypatch.setattr(
        PresentationLetterService,
        "_convert_docx_to_pdf",
        fake_convert,
    )


@pytest.mark.asyncio
async def test_director_can_list_templates(tmp_path):
    service = _service(tmp_path)

    templates = await service.list_templates(actor=_user(1, "Director de carrera"))

    assert {template.practice_type for template in templates} == {
        "Práctica de Estudio I",
        "Práctica de Estudio II",
        "Práctica Controlada",
    }


@pytest.mark.asyncio
async def test_director_can_update_template(tmp_path):
    repository = FakePresentationLetterRepository()
    service = _service(tmp_path, repository)

    updated = await service.update_template(
        practice_type="Práctica de Estudio I",
        payload=_template_payload(),
        actor=_user(1, "Director de carrera"),
    )

    assert updated.updated_by == 1
    assert updated.practice_description == "Descripción editable"
    assert repository.saved_template is updated


@pytest.mark.asyncio
async def test_template_reader_can_preview_unsaved_template_as_pdf(
    tmp_path,
    monkeypatch,
):
    repository = FakePresentationLetterRepository()
    service = _service(tmp_path, repository)
    payload = _template_payload()
    payload.title = "Vista previa sin guardar"
    captured = {}

    def fake_render_pdf(**kwargs):
        captured.update(kwargs)
        return b"%PDF-1.7\npreview"

    monkeypatch.setattr(service, "_render_pdf", fake_render_pdf)

    content = await service.preview_template(
        practice_type="Práctica de Estudio I",
        payload=payload,
        actor=_user(1, "Encargado de practica"),
    )

    assert content == b"%PDF-1.7\npreview"
    assert captured["template"].title == "Vista previa sin guardar"
    assert captured["student"].enrollment == "12345678924"
    assert repository.saved_template is None


@pytest.mark.asyncio
async def test_student_cannot_update_template(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.update_template(
            practice_type="Práctica de Estudio I",
            payload=_template_payload(),
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_preview_template(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.preview_template(
            practice_type="Práctica de Estudio I",
            payload=_template_payload(),
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_student_generates_practice_i_letter_with_real_user_data(
    tmp_path,
    monkeypatch,
):
    repository = FakePresentationLetterRepository()
    notifications = FakeNotificationService()
    service = _service(tmp_path, repository, notifications)
    _patch_pdf_conversion(
        monkeypatch,
        b"%PDF-1.7\nconverted-from-docx\nNombre Apellido\n12345670020",
    )

    letter = await service.generate_letter(
        actor=_user(10, "Estudiante"),
        payload=PresentationLetterGenerateRequest(
            practice_type="Práctica de Estudio I",
        ),
    )

    assert letter.id == 200
    assert letter.practice_type == "Práctica de Estudio I"
    assert letter.sent_at is not None
    assert notifications.notifications

    generated_path = tmp_path / letter.generated_file_path
    content = generated_path.read_bytes()
    assert content.startswith(b"%PDF-1.7")
    assert b"converted-from-docx" in content
    assert b"Nombre Apellido" in content
    assert b"12345670020" in content

    document = service._build_letter_document(
        template=repository.templates["Práctica de Estudio I"],
        student=_user(10, "Estudiante"),
        generated_at=datetime(2026, 6, 17, 10, 0, 0),
    )
    context = service._build_docx_context(document)
    text = " ".join(
        str(value)
        for value in (
            document["title"],
            document["subtitle"],
            *document["paragraphs"],
            *document["learning_outcomes"],
            document["insurance_clause"],
            document["signature_name"],
        )
    )
    normalized_text = " ".join(text.split())
    assert "CARTA DE PRESENTACIÓN" in text
    assert "Estudiante en Práctica de Estudios I" in text
    assert "Dirección de la Carrera de Ingeniería Civil Informática" in normalized_text
    assert "Nombre Apellido" in normalized_text
    assert "12345670020" in str(context["student_presentation"])
    assert "168 horas cronológicas" in normalized_text
    assert "Ley 16.744" in normalized_text
    assert "DS N°313" in normalized_text
    assert "Claudio Andrés Navarro Cruces" in text
    assert "Desarrollar la capacidad de interacción" in normalized_text
    assert "Duracion minima" not in text
    assert "Æ" not in text
    assert "Ø" not in text


@pytest.mark.asyncio
async def test_student_generates_practice_ii_letter_with_distinct_content(
    tmp_path,
    monkeypatch,
):
    service = _service(tmp_path)
    _patch_pdf_conversion(monkeypatch)

    letter = await service.generate_letter(
        actor=_user(10, "Estudiante"),
        payload=PresentationLetterGenerateRequest(
            practice_type="Práctica de Estudio II",
        ),
    )

    content = (tmp_path / letter.generated_file_path).read_bytes()
    assert b"from-docx" in content

    document = service._build_letter_document(
        template=service.repository.templates["Práctica de Estudio II"],
        student=_user(10, "Estudiante"),
        generated_at=datetime(2026, 6, 17, 10, 0, 0),
    )
    text = " ".join(
        str(value)
        for value in (
            document["title"],
            document["subtitle"],
            *document["paragraphs"],
            *document["learning_outcomes"],
        )
    )
    normalized_text = " ".join(text.split())
    assert "CARTA DE PRESENTACIÓN" in text
    assert "Estudiante en Práctica de Estudios II" in text
    assert "168 horas cronológicas" in normalized_text
    assert "Utilizar un lenguaje técnico y apropiado" in normalized_text
    assert "formación profesional" in normalized_text
    assert "Desarrollar la capacidad de interacción" not in normalized_text


def test_docx_context_uses_textual_template_fields(tmp_path):
    service = _service(tmp_path)
    template = service.repository.templates["Práctica de Estudio I"]
    document = service._build_letter_document(
        template=template,
        student=_user(10, "Estudiante"),
        generated_at=datetime(2026, 6, 17, 10, 0, 0),
    )

    context = service._build_docx_context(document)
    base_intro_xml = str(context["base_intro"])
    student_presentation_xml = str(context["student_presentation"])
    minimum_hours_clause_xml = str(context["minimum_hours_clause"])

    assert context["title"] == "CARTA DE PRESENTACIÓN"
    assert context["subtitle"] == "Estudiante en Práctica de Estudios I"
    assert "Reciba un cordial saludo" in base_intro_xml
    assert "Nombre Apellido" in student_presentation_xml
    assert "12345670020" in student_presentation_xml
    assert student_presentation_xml.count("<w:b/>") == 2
    assert "168" in minimum_hours_clause_xml
    assert "horas cronológicas" in minimum_hours_clause_xml
    assert minimum_hours_clause_xml.count("<w:b/>") == 2
    assert "Claudio Andrés Navarro Cruces" == context["signature_name"]


def test_rendered_docx_bolds_dynamic_student_values(tmp_path, monkeypatch):
    service = _service(tmp_path)

    def assert_docx_format(self, docx_path, output_dir):  # noqa: ANN001
        document = WordDocument(docx_path)
        student_paragraph = next(
            paragraph
            for paragraph in document.paragraphs
            if "Nombre Apellido" in paragraph.text
        )
        bold_text = " ".join(
            run.text
            for run in student_paragraph.runs
            if run.bold
        )
        regular_text = " ".join(
            run.text
            for run in student_paragraph.runs
            if not run.bold
        )

        assert "Nombre Apellido" in bold_text
        assert "12345670020" in bold_text
        assert "Por medio de la presente" in regular_text
        return b"%PDF-1.7\nformatted"

    monkeypatch.setattr(
        PresentationLetterService,
        "_convert_docx_to_pdf",
        assert_docx_format,
    )

    content = service._render_pdf(
        template=service.repository.templates["Práctica de Estudio I"],
        student=_user(10, "Estudiante"),
        generated_at=datetime(2026, 6, 17, 10, 0, 0),
    )

    assert content == b"%PDF-1.7\nformatted"


@pytest.mark.asyncio
async def test_missing_active_template_returns_clear_error(tmp_path):
    repository = FakePresentationLetterRepository()
    repository.templates.pop("Práctica de Estudio I")
    service = _service(tmp_path, repository)

    with pytest.raises(HTTPException) as exc:
        await service.generate_letter(
            actor=_user(10, "Estudiante"),
            payload=PresentationLetterGenerateRequest(
                practice_type="Práctica de Estudio I",
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "presentation_letter_template_not_found"


@pytest.mark.asyncio
async def test_student_can_download_own_letter(tmp_path):
    repository = FakePresentationLetterRepository()
    letter = _letter(student_id=10)
    repository.letters[letter.id] = letter
    (tmp_path / letter.generated_file_path).parent.mkdir(parents=True)
    (tmp_path / letter.generated_file_path).write_bytes(b"%PDF-1.4")
    service = _service(tmp_path, repository)

    download = await service.prepare_download(
        letter_id=letter.id,
        actor=_user(10, "Estudiante"),
    )

    assert download.path == tmp_path / letter.generated_file_path
    assert repository.saved_letter.downloaded_at is not None


@pytest.mark.asyncio
async def test_student_cannot_download_foreign_letter(tmp_path):
    repository = FakePresentationLetterRepository()
    repository.letters[1] = _letter(student_id=99)
    service = _service(tmp_path, repository)

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(letter_id=1, actor=_user(10, "Estudiante"))

    assert exc.value.status_code == 403
