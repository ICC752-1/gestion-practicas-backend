-- 1. Creacion de Enumeraciones (Enums)
CREATE TYPE "enumRole" AS ENUM ('Estudiante', 'Supervisor de practica', 'Encargado de practica', 'Director de carrera', 'Secretaria de Carrera');
CREATE TYPE "enumAction" AS ENUM ('INSERT', 'UPDATE', 'DELETE');
CREATE TYPE "enumEntity" AS ENUM ('Usuario', 'Practica', 'Documento', 'Presentacion', 'Estado', 'Rol', 'Configuracion');
CREATE TYPE "enumGender" AS ENUM ('Femenino', 'Masculino', 'Otro', 'No definido');
CREATE TYPE "enumModality" AS ENUM ('Presencial', 'Remoto', 'Hibrido');
CREATE TYPE "enumStatus" AS ENUM ('Pendiente', 'Aprobada', 'Rechazada', 'Incompleta');
CREATE TYPE "enumResult" AS ENUM ('Pendiente', 'Aprobada', 'Reprobado');
CREATE TYPE "enumExtension" AS ENUM ('pdf', 'docx', 'jpg', 'png', 'zip');
CREATE TYPE "enumCategory" AS ENUM ('Academico', 'Administrativo');

-- 2. Creacion de Tablas

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

CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(id),
    role_id INTEGER NOT NULL REFERENCES Roles(id),
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Internship (
    id SERIAL PRIMARY KEY,
    org_name VARCHAR(255) NOT NULL,
    sector VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    org_phone VARCHAR(255),
    web VARCHAR(255),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    schedule VARCHAR(255) NOT NULL,
    days VARCHAR(255) NOT NULL,
    modality "enumModality" NOT NULL,
    internship_address VARCHAR(255) NOT NULL,
    act_description VARCHAR(255) NOT NULL,
    ben_description VARCHAR(255) NOT NULL,
    amount INTEGER,
    upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_id INTEGER REFERENCES CurrentState(id),
    user_id INTEGER REFERENCES Users(id)
);

CREATE TABLE DocumentType (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_required BOOLEAN NOT NULL,
    category "enumCategory"
);

CREATE TABLE Document (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    extension "enumExtension" NOT NULL,
    upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    internship_id INTEGER REFERENCES Internship(id),
    type_id INTEGER REFERENCES DocumentType(id),
    user_id INTEGER REFERENCES Users(id)
);

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

-- 3. Insercion de datos iniciales minimos para testear autenticacion y autorizacion
INSERT INTO Roles (name, description) VALUES ('Estudiante', 'Rol correspondiente a estudiantes en practicas');

INSERT INTO Users (first_name, last_name, email, password_hash, rut, degree, cod_degree, sexo, phone, profession, position, departament, sup_phone)
VALUES ('Juan', 'Perez', 'juan.perez@correo.cl', '$argon2id$v=19$m=65536,t=3,p=4$bJbxhtRSiFdZs070A4Hv5w$Wunb39tfxReEtOvhcihtPHlzovAC+kJw2D/pCHpDDhg', '12.345.678-9', 'Ingenieria Civil Informatica', 'INF-001', 'Masculino', '+56912345678', 'Desarrollador', 'Practicante', 'TI', '+56998765432');
-- Nota: La contrasena hash corresponde a "my_secure_password"

INSERT INTO user_roles(user_id, role_id) VALUES (1, 1);


-- 4. Funcion del Trigger para automatizar la auditoria
CREATE OR REPLACE FUNCTION fn_audit_business_logic()
RETURNS TRIGGER AS $$
DECLARE
    current_user_id INTEGER;
    entity_enum "enumEntity";
BEGIN
    entity_enum := CASE lower(TG_TABLE_NAME)
        WHEN 'users' THEN 'Usuario'::"enumEntity"
        WHEN 'internship' THEN 'Practica'::"enumEntity"
        WHEN 'document' THEN 'Documento'::"enumEntity"
        WHEN 'presentation' THEN 'Presentacion'::"enumEntity"
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
        VALUES ('INSERT', entity_enum, 'Creacion de nuevo registro', to_jsonb(NEW), NEW.id, current_user_id);
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO LogAction (action, entity, description, old_value, new_value, entity_id, user_id)
        VALUES ('UPDATE', entity_enum, 'Actualizacion de datos', to_jsonb(OLD), to_jsonb(NEW), NEW.id, current_user_id);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO LogAction (action, entity, description, old_value, entity_id, user_id)
        VALUES ('DELETE', entity_enum, 'Eliminacion de registro', to_jsonb(OLD), OLD.id, current_user_id);
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER tr_audit_user AFTER INSERT OR UPDATE OR DELETE ON Users FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_internship AFTER INSERT OR UPDATE OR DELETE ON Internship FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_document AFTER INSERT OR UPDATE OR DELETE ON Document FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
CREATE TRIGGER tr_audit_presentation AFTER INSERT OR UPDATE OR DELETE ON Presentation FOR EACH ROW EXECUTE FUNCTION fn_audit_business_logic();
