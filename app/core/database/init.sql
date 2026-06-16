-- 1. Creación de Enumeraciones (Enums)
CREATE TYPE "enumRole" AS ENUM ('Estudiante', 'Supervisor de practica', 'Encargado de practica', 'Director de carrera', 'Secretaria de Carrera', 'FICA', 'Superadmin');
CREATE TYPE "enumAction" AS ENUM ('INSERT', 'UPDATE', 'DELETE');
CREATE TYPE "enumEntity" AS ENUM ('Usuario', 'Práctica', 'Documento', 'Presentación', 'Estado', 'Rol', 'Configuración');
CREATE TYPE "enumGender" AS ENUM ('Femenino', 'Masculino', 'Otro', 'No definido');
CREATE TYPE "enumModality" AS ENUM ('Presencial', 'Remoto', 'Híbrido');
CREATE TYPE "enumStatus" AS ENUM ('Pendiente', 'Aprobada', 'Rechazada', 'Incompleta');
CREATE TYPE "enumResult" AS ENUM ('Pendiente', 'Aprobada', 'Reprobado');
CREATE TYPE "enumExtension" AS ENUM ('pdf', 'docx', 'jpg', 'png', 'zip');
CREATE TYPE "exceptable_rule_enum" AS ENUM ('school_insurance', 'sequentiality', 'sequentiality_thesis', 'parallel_course');
CREATE TYPE "enumDocumentStatus" AS ENUM ('uploaded', 'observed', 'approved', 'deleted');

CREATE TYPE "enumCategory" AS ENUM ('Académico', 'Administrativo');
CREATE TYPE "enumStudentInternshipType" AS ENUM ('Práctica de Estudio I', 'Práctica de Estudio II', 'Tesis', 'Práctica Controlada');
CREATE TYPE "enumStudentInternshipStatus" AS ENUM ('Pendiente', 'Habilitada', 'En revisión', 'Aprobada', 'Rechazada');
CREATE TYPE "enumInternshipPeriod" AS ENUM ('Semestre', 'Verano', 'Invierno');

CREATE TYPE "enumNotificationEventType" AS ENUM ('internship_approved', 'internship_rejected', 'internship_derived', 'requirement_status_changed', 'custom');
CREATE TYPE "enumNotificationStatus" AS ENUM ('simulated', 'pending', 'sent', 'failed');

CREATE TYPE "registration_requirement_enum" AS ENUM ('school_insurance', 'induction');
CREATE TYPE "content_status_enum" AS ENUM ('draft', 'published');

-- 2. Creación de Tablas

CREATE TABLE Roles (
    id SERIAL PRIMARY KEY,
    name "enumRole" NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CurrentState (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL
);

INSERT INTO CurrentState (title, description) VALUES
    ('Pendiente', 'La práctica existe como estado del proceso, pero aún no inicia su tramitación en el sistema.'),
    ('En revisión DIRAE', 'La práctica presenta observaciones en sus plazos y fue derivada a la Dirección de Registro Académico y Estudiantil.'),
    ('En revisión', 'La práctica fue registrada y se encuentra en revisión administrativa.'),
    ('Aprobada', 'La práctica fue aprobada durante la revisión administrativa.'),
    ('Rechazada', 'La práctica fue rechazada durante la revisión administrativa.');

CREATE TABLE Users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rut VARCHAR(100) UNIQUE NOT NULL,
    degree VARCHAR(255),
    cod_degree VARCHAR(100),
    sexo "enumGender",
    phone VARCHAR(100),
    profession VARCHAR(100),
    position VARCHAR(100),
    departament VARCHAR(100),
    sup_phone VARCHAR(100),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    jti VARCHAR(255) UNIQUE NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_tokens_jti ON refresh_tokens(jti);

CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id),
    role_id INTEGER NOT NULL REFERENCES Roles(id),
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE studentInternshipRequirement (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id),
    type "enumStudentInternshipType" NOT NULL,
    status "enumStudentInternshipStatus" NOT NULL DEFAULT 'Pendiente',
    status_updated_at TIMESTAMP,
    status_updated_by INTEGER REFERENCES Users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (user_id, type)
);

CREATE TABLE Internship (
    id SERIAL PRIMARY KEY,
    org_name VARCHAR(255) NOT NULL,
    sector VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    org_phone VARCHAR(255),
    web VARCHAR(255),
    supervisor_name VARCHAR(255) NOT NULL,
    supervisor_profession VARCHAR(255) NOT NULL,
    supervisor_position VARCHAR(255) NOT NULL,
    supervisor_department VARCHAR(255) NOT NULL,
    supervisor_email VARCHAR(255) NOT NULL,
    supervisor_phone VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    schedule VARCHAR(255) NOT NULL,
    days VARCHAR(255) NOT NULL,
    modality "enumModality" NOT NULL,
    internship_address VARCHAR(255) NOT NULL,
    act_description VARCHAR(255) NOT NULL,
    ben_description VARCHAR(255) NOT NULL,
    amount INTEGER,
    internship_period "enumInternshipPeriod", 
    internship_type "enumStudentInternshipType",  
    has_school_insurance BOOLEAN,
    is_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    cancelled_by INTEGER REFERENCES Users(id),
    cancellation_reason TEXT,

    upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_id INTEGER REFERENCES CurrentState(id),
    user_id INTEGER REFERENCES Users(id)
);

CREATE TABLE internship_status_history (
    id SERIAL PRIMARY KEY,
    internship_id INTEGER NOT NULL REFERENCES Internship(id),
    previous_status_id INTEGER REFERENCES CurrentState(id),
    new_status_id INTEGER NOT NULL REFERENCES CurrentState(id),
    actor_id INTEGER REFERENCES Users(id),
    reason TEXT,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE DocumentType (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_required BOOLEAN NOT NULL,
    category "enumCategory",
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE Document (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    extension "enumExtension" NOT NULL,
    status "enumDocumentStatus" NOT NULL DEFAULT 'uploaded',
    size_bytes INTEGER NOT NULL,
    upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    internship_id INTEGER NOT NULL REFERENCES Internship(id),
    type_id INTEGER NOT NULL REFERENCES DocumentType(id),
    user_id INTEGER NOT NULL REFERENCES Users(id),
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES Users(id),
    review_comment TEXT,
    deleted_at TIMESTAMP,
    deleted_by INTEGER REFERENCES Users(id)
);

CREATE INDEX ix_document_internship_id ON Document(internship_id);
CREATE INDEX ix_document_user_id ON Document(user_id);
CREATE INDEX ix_document_status ON Document(status);

INSERT INTO DocumentType (name, description, is_required, category) VALUES
    ('Formulario de inscripción', 'Formulario de inscripción de práctica firmado o respaldado.', TRUE, 'Académico'),
    ('Carta de aceptación', 'Documento emitido por la organización receptora.', TRUE, 'Administrativo'),
    ('Seguro escolar', 'Respaldo administrativo de cobertura cuando corresponda.', FALSE, 'Administrativo'),
    ('Documento complementario', 'Documento adicional requerido para regularizar o respaldar el caso.', FALSE, 'Administrativo');

CREATE TABLE Presentation (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    modality "enumModality" NOT NULL,
    status "enumStatus" NOT NULL,
    result "enumResult",
    comments TEXT,
    internship_id INTEGER REFERENCES Internship(id),
    user_id INTEGER REFERENCES Users(id)
);

CREATE TABLE LogAction (
id SERIAL PRIMARY KEY,
action "enumAction" NOT NULL,
entity "enumEntity" NOT NULL,
timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
description TEXT NOT NULL,
old_value JSONB,
new_value JSONB,
entity_id INTEGER NOT NULL,
user_id INTEGER REFERENCES Users(id)
);

CREATE TABLE notification (
id SERIAL PRIMARY KEY,
recipient_user_id INTEGER REFERENCES Users(id),
recipient_email VARCHAR(255),
event_type "enumNotificationEventType" NOT NULL,
subject VARCHAR(255) NOT NULL,
content TEXT NOT NULL,
status "enumNotificationStatus" NOT NULL,
payload JSONB,
created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
sent_at TIMESTAMP,
read_at TIMESTAMP
);

CREATE INDEX ix_notification_recipient_user_id ON notification(recipient_user_id);
CREATE INDEX ix_notification_read_at ON notification(read_at);

CREATE TABLE supervisor_evaluation_invitations (
    id SERIAL PRIMARY KEY,
    internship_id INTEGER NOT NULL REFERENCES Internship(id) ON DELETE CASCADE,
    supervisor_name_snapshot VARCHAR(255) NOT NULL,
    supervisor_email_snapshot VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES Users(id) ON DELETE SET NULL
);

CREATE INDEX ix_supervisor_evaluation_invitations_internship_id ON supervisor_evaluation_invitations(internship_id);
CREATE INDEX ix_supervisor_evaluation_invitations_token_hash ON supervisor_evaluation_invitations(token_hash);

CREATE TABLE supervisor_evaluations (
    id SERIAL PRIMARY KEY,
    internship_id INTEGER UNIQUE NOT NULL REFERENCES Internship(id) ON DELETE CASCADE,
    invitation_id INTEGER UNIQUE REFERENCES supervisor_evaluation_invitations(id) ON DELETE SET NULL,
    supervisor_name_snapshot VARCHAR(255) NOT NULL,
    supervisor_email_snapshot VARCHAR(255) NOT NULL,
    criteria_scores JSONB NOT NULL,
    observations TEXT,
    recommendation VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'submitted',
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_supervisor_evaluations_internship_id ON supervisor_evaluations(internship_id);

CREATE TABLE internship_exceptions (
    id SERIAL PRIMARY KEY,
    internship_id INTEGER NOT NULL REFERENCES Internship(id) ON DELETE CASCADE,
    rule "exceptable_rule_enum" NOT NULL,
    reason TEXT NOT NULL,
    authorized_by INTEGER REFERENCES Users(id) ON DELETE SET NULL,
    authorized_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);    

CREATE TABLE student_registration_requirements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id),
    requirement "registration_requirement_enum" NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMP,
    updated_by INTEGER REFERENCES Users(id),

    UNIQUE (user_id, requirement)
);

CREATE TABLE induction_content_versions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status "content_status_enum" NOT NULL DEFAULT 'draft',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    min_score INTEGER NOT NULL DEFAULT 5,
    requires_retake BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE induction_videos (
    id SERIAL PRIMARY KEY,
    content_version_id INTEGER NOT NULL REFERENCES induction_content_versions(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    video_url VARCHAR(500) NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE induction_questions (
    id SERIAL PRIMARY KEY,
    content_version_id INTEGER NOT NULL REFERENCES induction_content_versions(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE induction_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    content_version_id INTEGER NOT NULL REFERENCES induction_content_versions(id) ON DELETE CASCADE,
    answers JSONB NOT NULL,
    score INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION fn_create_student_internship_requirements()
RETURNS TRIGGER AS $$
DECLARE
    role_name "enumRole";
BEGIN
    SELECT name INTO role_name
    FROM Roles
    WHERE id = NEW.role_id;

    IF role_name = 'Estudiante' THEN
        INSERT INTO StudentInternshipRequirement (user_id, type)
        VALUES
            (NEW.user_id, 'Práctica de Estudio I'),
            (NEW.user_id, 'Práctica de Estudio II'),
            (NEW.user_id, 'Tesis'),
            (NEW.user_id, 'Práctica Controlada')
        ON CONFLICT (user_id, type) DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_create_student_internship_requirements
AFTER INSERT ON user_roles
FOR EACH ROW
EXECUTE FUNCTION fn_create_student_internship_requirements();

-- 3. Insercion de datos iniciales minimos para testear autenticacion y autorizacion
INSERT INTO Roles (name, description) VALUES ('Estudiante', 'Rol correspondiente a estudiantes en practicas');
INSERT INTO Roles (name, description) VALUES ('Director de carrera', 'Rol correspondiente al director de la carrera perteneciente a FICA');
INSERT INTO Roles (name, description) VALUES ('Supervisor de practica', 'Rol correspondiente al supervisor externo de practicas');
INSERT INTO Roles (name, description) VALUES ('Encargado de practica', 'Rol correspondiente al encargado de practicas');
INSERT INTO Roles (name, description) VALUES ('Secretaria de Carrera', 'Rol correspondiente a secretaria de carrera');
INSERT INTO Roles (name, description) VALUES ('FICA', 'Rol institucional de consulta agregada transversal');
INSERT INTO Roles (name, description) VALUES ('Superadmin', 'Rol tecnico para administracion de usuarios y roles');

INSERT INTO Users (first_name, last_name, email, password_hash, rut, degree, cod_degree, sexo, phone, profession, position, departament, sup_phone)
VALUES ('Juan', 'Perez', 'juan.perez@correo.cl', '$argon2id$v=19$m=65536,t=3,p=4$bJbxhtRSiFdZs070A4Hv5w$Wunb39tfxReEtOvhcihtPHlzovAC+kJw2D/pCHpDDhg', '12.345.678-9', 'Ingenieria Civil Informatica', 'INF-001', 'Masculino', '+56912345678', 'Desarrollador', 'Practicante', 'TI', '+56998765432');

INSERT INTO Users (first_name, last_name, email, password_hash, rut)
VALUES ('Claudio', 'Navarro', 'claudio.navarro@ufrontera.cl', '$argon2id$v=19$m=65536,t=3,p=4$bJbxhtRSiFdZs070A4Hv5w$Wunb39tfxReEtOvhcihtPHlzovAC+kJw2D/pCHpDDhg', '14.283.070-1');
-- Nota: La contrasena hash corresponde a "my_secure_password"

INSERT INTO user_roles(user_id, role_id) VALUES (1, 1);
INSERT INTO user_roles(user_id, role_id) VALUES (2, 2);

-- Contenido minimo de induccion para flujos demo/Insomnia.
-- Permite que el estudiante complete el prerrequisito inexceptuable antes
-- de aprobar una Practica de Estudio I.
INSERT INTO induction_content_versions (title, description, status, is_active, min_score, published_at)
VALUES (
    'Induccion obligatoria demo',
    'Contenido minimo para validar el flujo de induccion en ambiente local.',
    'published',
    TRUE,
    1,
    CURRENT_TIMESTAMP
);

INSERT INTO induction_videos (content_version_id, title, video_url, "order")
SELECT id, 'Video introductorio demo', 'https://example.com/induccion-demo', 1
FROM induction_content_versions
WHERE title = 'Induccion obligatoria demo';

INSERT INTO induction_questions (content_version_id, question_text, options, correct_answer, "order")
SELECT
    id,
    'Confirma que revisaste la induccion obligatoria antes de tramitar tu practica.',
    '{"accept": "Entiendo y acepto", "reject": "No acepto"}'::jsonb,
    'accept',
    1
FROM induction_content_versions
WHERE title = 'Induccion obligatoria demo';

-- 4. Función del Trigger para automatizar la auditoría
CREATE OR REPLACE FUNCTION fn_audit_business_logic()
RETURNS TRIGGER AS $$
DECLARE
    current_user_id INTEGER;
    entity_enum "enumEntity";
BEGIN
    entity_enum := CASE lower(TG_TABLE_NAME)
        WHEN 'users' THEN 'Usuario'::"enumEntity"
        WHEN 'internship' THEN 'Práctica'::"enumEntity"
        WHEN 'internship_exceptions' THEN 'Práctica':: "enumEntity"
        WHEN 'document' THEN 'Documento'::"enumEntity"
        WHEN 'presentation' THEN 'Presentación'::"enumEntity"
        WHEN 'roles' THEN 'Rol'::"enumEntity"
        WHEN 'currentstate' THEN 'Estado'::"enumEntity"
        ELSE NULL
    END;

    IF entity_enum IS NULL THEN
        RAISE EXCEPTION 'No enumEntity mapping for table %', TG_TABLE_NAME
            USING ERRCODE = '22023';
    END IF;

    BEGIN
        current_user_id := current_setting('app.current_user_id')::INTEGER;
    EXCEPTION WHEN OTHERS THEN
        current_user_id := NULL;
    END;

    IF (TG_OP = 'INSERT') THEN
        INSERT INTO LogAction (action, entity, description, new_value, entity_id, user_id)
        VALUES ('INSERT', entity_enum, 'Creación de nuevo registro', to_jsonb(NEW), NEW.id, current_user_id);
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO LogAction (action, entity, description, old_value, new_value, entity_id, user_id)
        VALUES ('UPDATE', entity_enum, 'Actualización de datos', to_jsonb(OLD), to_jsonb(NEW), NEW.id, current_user_id);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO LogAction (action, entity, description, old_value, entity_id, user_id)
        VALUES ('DELETE', entity_enum, 'Eliminación de registro', to_jsonb(OLD), OLD.id, current_user_id);
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER tr_audit_user AFTER INSERT OR UPDATE OR DELETE ON Users FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_internship AFTER INSERT OR UPDATE OR DELETE ON Internship FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_document AFTER INSERT OR UPDATE OR DELETE ON Document FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_presentation AFTER INSERT OR UPDATE OR DELETE ON Presentation FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_exceptions AFTER INSERT OR UPDATE OR DELETE ON internship_exceptions FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
