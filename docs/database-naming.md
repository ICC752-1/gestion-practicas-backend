# Convencion de nombres BD/ORM

Este documento fija la decision tecnica para la tarea 10.10: alinear los
nombres reales de PostgreSQL, los modelos SQLAlchemy y la documentacion antes de
ampliar los modulos de documentos y auditoria.

## Decision

- Los nombres de tablas existentes se tratan como identificadores PostgreSQL no
  citados. Por eso `CREATE TABLE CurrentState` se almacena realmente como
  `currentstate`.
- Los modelos SQLAlchemy deben usar en `__tablename__` el nombre real almacenado
  por PostgreSQL, en minusculas.
- No se deben crear tablas nuevas con identificadores citados ni con tildes.
- Para tablas nuevas, usar nombres no citados en `lower_snake_case`.
- Los nombres de enums PostgreSQL ya existentes se mantienen citados y con su
  capitalizacion actual, por ejemplo `"enumStudentInternshipType"`, porque el
  esquema vigente y los modelos `PGEnum(..., name=...)` dependen de esos nombres.
- Las tildes se permiten en valores de negocio visibles para usuarios, como
  `'Práctica de Estudio I'`, pero no en nombres de tablas, columnas, funciones o
  constraints.

## Comparativa del esquema actual

| Entidad funcional | Definicion en `init.sql` | Nombre real PostgreSQL | `__tablename__` actual | Estado |
| --- | --- | --- | --- | --- |
| Roles | `Roles` | `roles` | `roles` | Alineado |
| Usuarios | `Users` | `users` | `users` | Alineado |
| Roles de usuario | `user_roles` | `user_roles` | `user_roles` | Alineado |
| Estado de practica | `CurrentState` | `currentstate` | `currentstate` | Alineado, nombre legado sin guion bajo |
| Requisito de practica | `StudentInternshipRequirement` | `studentinternshiprequirement` | `studentinternshiprequirement` | Alineado, nombre legado sin guion bajo |
| Practica | `Internship` | `internship` | `internship` | Alineado |
| Historial de estado | `internship_status_history` | `internship_status_history` | `internship_status_history` | Alineado |
| Tipo de documento | `DocumentType` | `documenttype` | Sin modelo ORM | Pendiente de modelar |
| Documento | `Document` | `document` | Sin modelo ORM | Pendiente de modelar |
| Presentacion | `Presentation` | `presentation` | Sin modelo ORM | Pendiente de modelar |
| Auditoria general | `LogAction` | `logaction` | Sin modelo ORM | Pendiente de modelar |
| Notificacion | `notification` | `notification` | `notification` | Alineado |

## Impacto sobre tablas relevantes

- `CurrentState`: no requiere cambio de runtime. Mantener `__tablename__ =
  "currentstate"` y referencias `ForeignKey("currentstate.id")`.
- `Internship`: no requiere cambio de runtime. Mantener `__tablename__ =
  "internship"` y referencias hacia `users` y `currentstate`.
- `StudentInternshipRequirement`: no requiere cambio de runtime. Mantener
  `__tablename__ = "studentinternshiprequirement"` mientras no exista una
  migracion formal.
- `Document`: si se implementa un modelo ORM antes de migrar el esquema, debe
  mapear a `__tablename__ = "document"`.
- `DocumentType`: si se implementa un modelo ORM antes de migrar el esquema,
  debe mapear a `__tablename__ = "documenttype"`.
- `LogAction`: si se implementa un modelo ORM antes de migrar el esquema, debe
  mapear a `__tablename__ = "logaction"`.

## Migracion

No se recomienda renombrar tablas en Sprint 10. La migracion tendria impacto en:

- `app/core/database/init.sql`;
- claves foraneas y triggers de auditoria;
- modelos SQLAlchemy y `ForeignKey(...)`;
- datos ya inicializados en ambientes donde el volumen PostgreSQL fue creado con
  el esquema actual.

Si mas adelante se decide normalizar nombres legados a `lower_snake_case`, la
migracion minima debe ser explicita y versionada. Ejemplos:

- `currentstate` -> `current_state`;
- `studentinternshiprequirement` -> `student_internship_requirement`;
- `documenttype` -> `document_type`;
- `logaction` -> `log_action`.

Hasta que exista esa migracion, el criterio oficial es mantener los nombres
reales actuales y documentar cualquier tabla nueva en esta convencion.

## Checklist para modelos nuevos

1. Verificar el nombre real con la regla de PostgreSQL: identificadores no
   citados se pliegan a minusculas.
2. Definir `__tablename__` con el nombre real de la tabla.
3. Usar `lower_snake_case` para tablas nuevas.
4. Evitar tildes, espacios y mayusculas significativas en identificadores.
5. Mantener `PGEnum(..., name="...")` exactamente igual al tipo existente en
   `init.sql`.
6. Documentar si una tabla nueva queda como legado temporal o si incluye una
   migracion formal.
