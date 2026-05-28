# Reglas de Negocio: Gestión de Prácticas

## RN-01: Obligatoriedad de Seguro Escolar según Período de Práctica

### Descripción
La validación del seguro escolar garantiza la cobertura de accidentes de los estudiantes durante el desarrollo de sus actividades profesionales. La obligatoriedad de este seguro varía estrictamente según la naturaleza temporal del período en el que se ejecuta la práctica.

### Definición de la Regla
* **Práctica Semestral (`internship_period`: "Semestre"):** El seguro escolar **no es requerido** de forma obligatoria por parte de la plataforma para registrar la práctica, dado que el estudiante mantiene la carga académica y cobertura regular del periodo lectivo.
* **Práctica Estival o de Verano (`internship_period`: "Verano"):** El seguro escolar es **estrictamente obligatorio**. No se permitirá el registro de ninguna práctica de verano que no cuente con la declaración explícita de cobertura de seguro.
    * *Excepción Administrativa:* Contemplada para ser implementada a nivel de sistema en el **Sprint 9** (gestión de casos excepcionales por secretaría de estudios o dirección de carrera).

### Base Legal y Contexto Institucional
* **Decreto Supremo N° 313:** Incluye a los estudiantes en el Seguro Escolar contra Accidentes del Trabajo y Enfermedades Profesionales de forma regular durante el año académico.
* **Reglamento de Prácticas FICA:** Dispone que toda actividad realizada fuera del periodo académico ordinario (periodo estival) requiere una extensión explícita de la cobertura del seguro para resguardar la integridad del alumno y la responsabilidad de la institución.

---

## Especificación Técnica (API Contract)

### Endpoint: `POST /internships`

#### 1. Flujo de Rechazo (Práctica de Verano sin Seguro)
Si se intenta registrar una práctica en periodo estival (`"internship_period": "Verano"`) omitiendo o marcando el seguro como falso (`"has_school_insurance": false`), el sistema denegará la petición.

* **Código de Respuesta:** `400 Bad Request`
* **Cuerpo de la Respuesta (Payload):**
```json
{
  "field": "has_school_insurance",
  "message": "El seguro escolar es obligatorio para prácticas del período estival."
}

#### 2. Flujo Exitoso (Creación de Registro)
El sistema procesará y creará el registro correctamente en la base de datos (retornando `201 Created`) bajo los siguientes escenarios de cumplimiento:

##### Caso A: Práctica Semestral (Seguro Opcional/No Requerido)
Permite el registro sin necesidad de contar con seguro escolar activo.

* **Código de Respuesta:** `201 Created`
* **Ejemplo de Petición (Payload):**
```json
{
  "org_name": "Empresa SA",
  "sector": "Tecnología",
  "address": "Av. Principal 123",
  "city": "Temuco",
  "start_date": "2026-06-01",
  "end_date": "2026-08-31",
  "schedule": "08:00 - 17:00",
  "days": "Lunes a Viernes",
  "modality": "Presencial",
  "internship_address": "Av. Principal 123",
  "act_description": "Desarrollo de software backend",
  "ben_description": "Aplicar conocimientos académicos",
  "internship_period": "Semestre",
  "internship_type": "Práctica de Estudio I",
  "has_school_insurance": false
}

#### caso B: Práctica de Verano con Seguro (Obligatorio Cumplido)
Permite el registro en periodo estival siempre que se declare explícitamente la posesión del seguro.

* Código de Respuesta: 201 Created

* Ejemplo de Petición (Payload):

{
  "org_name": "Empresa SA",
  "sector": "Tecnología",
  "address": "Av. Principal 123",
  "city": "Temuco",
  "start_date": "2026-06-01",
  "end_date": "2026-08-31",
  "schedule": "08:00 - 17:00",
  "days": "Lunes a Viernes",
  "modality": "Presencial",
  "internship_address": "Av. Principal 123",
  "act_description": "Desarrollo de software backend",
  "ben_description": "Aplicar conocimientos académicos",
  "internship_period": "Verano",
  "internship_type": "Práctica de Estudio I",
  "has_school_insurance": true
}