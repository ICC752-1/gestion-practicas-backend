# Plan de normalización de nombres BD/ORM

Fecha: 09/06/2026

## Alcance

Este documento responde al issue #97 y define la convención objetivo antes de ampliar los módulos de documentos y auditoría.

La base no tiene un entorno productivo real que deba conservar datos históricos. Por eso la opción preferida para implementar el cambio es normalizar el esquema desde `init.sql`, actualizar los modelos SQLAlchemy y recrear las bases locales o de prueba desde cero. Si más adelante existe un volumen con datos valiosos, se debe usar una migración explícita antes de aplicar estos cambios.

## Convención objetivo

- Objetos SQL: `lower_snake_case`, sin tildes, sin comillas y en inglés.
- Tablas de entidades: plural cuando representen colecciones del dominio.
- Tablas de unión o historial: `lower_snake_case` descriptivo.
- Tipos enum de PostgreSQL: `enum_<domain>` en `lower_snake_case`.
- Valores de enum: se mantienen como etiquetas de negocio cuando forman parte del contrato funcional o de la API, por ejemplo `Práctica de Estudio I` o `Secretaria de Carrera`.
- Modelos SQLAlchemy: `__tablename__` debe coincidir exactamente con el nombre físico de la tabla.
- Llaves foráneas SQLAlchemy: usar el mismo nombre físico, por ejemplo `ForeignKey("internships.id")`.

La decisión evita identificadores PostgreSQL citados y sensibles a mayúsculas. También evita la forma actual donde `CREATE TABLE CurrentState` termina creando físicamente `currentstate` porque PostgreSQL convierte identificadores no citados a minúsculas.

## Tabla comparativa

| Concepto | `init.sql` actual | ORM actual | Nombre objetivo | Acción |
| --- | --- | --- | --- | --- |
| Roles | `Roles` | `roles` | `roles` | Ajustar texto SQL a minúscula. |
| Usuarios | `Users` | `users` | `users` | Ajustar texto SQL a minúscula. |
| Roles de usuario | `user_roles` | `user_roles` | `user_roles` | Mantener. |
| Estado de práctica | `CurrentState` | `currentstate` | `current_states` | Renombrar tabla y FK. |
| Requisito de práctica | `StudentInternshipRequirement` | `studentinternshiprequirement` | `student_internship_requirements` | Renombrar tabla y FK. |
| Práctica | `Internship` | `internship` | `internships` | Renombrar tabla y FK. |
| Historial de estados | `internship_status_history` | `internship_status_history` | `internship_status_history` | Mantener. |
| Tipo de documento | `DocumentType` | Sin modelo activo | `document_types` | Usar nombre objetivo antes de crear modelos. |
| Documento | `Document` | Sin modelo activo | `documents` | Usar nombre objetivo antes de crear modelos. |
| Presentación | `Presentation` | Sin modelo activo | `presentations` | Renombrar en SQL y triggers. |
| Auditoría general | `LogAction` | Sin modelo activo | `log_actions` | Renombrar tabla e inserts del trigger. |
| Notificación | `notification` | `notification` | `notifications` | Renombrar tabla y ORM. |

## Enums PostgreSQL

| Tipo actual | Tipo objetivo |
| --- | --- |
| `"enumRole"` | `enum_role` |
| `"enumAction"` | `enum_action` |
| `"enumEntity"` | `enum_entity` |
| `"enumGender"` | `enum_gender` |
| `"enumModality"` | `enum_modality` |
| `"enumStatus"` | `enum_status` |
| `"enumResult"` | `enum_result` |
| `"enumExtension"` | `enum_extension` |
| `"enumCategory"` | `enum_category` |
| `"enumStudentInternshipType"` | `enum_student_internship_type` |
| `"enumStudentInternshipStatus"` | `enum_student_internship_status` |
| `"enumInternshipPeriod"` | `enum_internship_period` |
| `"enumNotificationEventType"` | `enum_notification_event_type` |
| `"enumNotificationStatus"` | `enum_notification_status` |

## Impacto por archivo

| Archivo | Cambio esperado |
| --- | --- |
| `app/core/database/init.sql` | Renombrar tablas, referencias, triggers, funciones y tipos enum. |
| `app/modules/*/models/*.py` | Alinear `__tablename__`, `ForeignKey(...)` y nombres `PGEnum`. |
| `tests/modules/*` | Agregar o ajustar pruebas de contrato para validar nombres de tablas, FKs y enums. |
| `docs/development-standards.md` | Mantener la regla de nombres como fuente de verdad para futuros modelos. |
| `docs/api-contracts.md` | No debería cambiar salvo que se decida modificar valores de enum expuestos por API. |

## Estrategia de implementación

1. Actualizar `init.sql` con los nombres objetivo.
2. Actualizar modelos ORM existentes: `Role`, `User`, `UserRole`, `CurrentState`, `StudentInternshipRequirement`, `Internship`, `InternshipStatusHistory` y `Notification`.
3. Dejar los nombres objetivo listos para modelos futuros de documents: `documents` y `document_types`.
4. Actualizar la función `fn_create_student_internship_requirements`.
5. Actualizar la función `fn_audit_business_logic` y los triggers para apuntar a `users`, `internships`, `documents`, `presentations` y `log_actions`.
6. Agregar una prueba de contrato que compare:
   - tablas declaradas en SQLAlchemy;
   - nombres esperados por `init.sql`;
   - nombres de enum usados por columnas ORM.
7. Recrear la base local y de CI desde cero, porque no hay producción real que migrar.
8. Ejecutar `uv run ruff check .` y `uv run pytest --tb=short`.

## Migración mínima

Ruta preferida mientras no exista producción real:

1. Detener los servicios locales.
2. Eliminar solo el volumen local de PostgreSQL asociado al entorno de desarrollo.
3. Levantar de nuevo el stack para que `init.sql` cree el esquema normalizado.
4. Reseed con los datos mínimos del propio `init.sql`.

Ruta alternativa si se deben preservar datos:

1. Respaldar la base.
2. Aplicar `ALTER TABLE ... RENAME TO ...` para tablas.
3. Aplicar `ALTER TYPE ... RENAME TO ...` para enums.
4. Actualizar funciones y triggers en la misma migración.
5. Validar con consultas de conteo y pruebas de API.

## Riesgos

- El proyecto no tiene Alembic u otra capa de migraciones. Si se aplica el cambio sobre una base con datos existentes, `init.sql` no actualizará el volumen ya inicializado.
- Los triggers de auditoría dependen de nombres de tabla; deben cambiar junto con las tablas o fallarán en tiempo de ejecución.
- Cambiar valores de enum visibles en API, como roles o tipos de práctica, puede romper frontend y pruebas funcionales. Ese cambio queda fuera de este plan.
- Los módulos `documents`, `presentation` y `log_actions` aún no tienen modelos completos, por lo que conviene normalizar los nombres antes de implementarlos.

## Checklist para nuevos modelos

- `__tablename__` usa plural `lower_snake_case`.
- Toda `ForeignKey` usa el nombre físico real de la tabla.
- Todo `PGEnum(..., name=...)` usa `enum_<domain>` en `lower_snake_case`.
- No se introducen identificadores SQL citados por mayúsculas.
- Si el cambio altera esquema existente, se crea migración o se documenta el reinicio de base local.
- Las pruebas incluyen al menos una aserción de contrato sobre tabla, FK o enum.
