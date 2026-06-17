-- Backfill para bases existentes antes de crear el índice parcial de Sprint 11.3.
-- Objetivo:
-- 1. Agregar la columna blocks_new_registration sin romper filas previas.
-- 2. Liberar prácticas rechazadas o anuladas.
-- 3. Conservar como bloqueante solo la solicitud vigente más reciente por
--    estudiante + tipo, evitando colisiones al crear el índice único parcial.

ALTER TABLE internship
ADD COLUMN IF NOT EXISTS blocks_new_registration BOOLEAN;

-- Estado base: todo no bloquea hasta resolver el backfill.
UPDATE internship
SET blocks_new_registration = FALSE
WHERE blocks_new_registration IS NULL;

-- Solicitudes anuladas o rechazadas no deben bloquear nuevas creaciones.
UPDATE internship AS i
SET blocks_new_registration = FALSE
FROM currentstate AS cs
WHERE cs.id = i.status_id
  AND (
    i.is_cancelled IS TRUE
    OR cs.title = 'Rechazada'
  );

-- Entre las solicitudes restantes, solo la más reciente por estudiante + tipo
-- conserva el bloqueo. El resto se libera para evitar duplicados históricos.
WITH ranked AS (
    SELECT
        i.id,
        ROW_NUMBER() OVER (
            PARTITION BY i.user_id, i.internship_type
            ORDER BY i.upload_date DESC, i.id DESC
        ) AS row_number
    FROM internship AS i
    LEFT JOIN currentstate AS cs ON cs.id = i.status_id
    WHERE COALESCE(i.is_cancelled, FALSE) IS FALSE
      AND COALESCE(cs.title, '') <> 'Rechazada'
)
UPDATE internship AS i
SET blocks_new_registration = (ranked.row_number = 1)
FROM ranked
WHERE ranked.id = i.id;

ALTER TABLE internship
ALTER COLUMN blocks_new_registration SET DEFAULT TRUE;

UPDATE internship
SET blocks_new_registration = TRUE
WHERE blocks_new_registration IS NULL;

ALTER TABLE internship
ALTER COLUMN blocks_new_registration SET NOT NULL;

DROP INDEX IF EXISTS uq_internship_blocking_type_per_student;

CREATE UNIQUE INDEX uq_internship_blocking_type_per_student
ON internship(user_id, internship_type)
WHERE blocks_new_registration IS TRUE;
