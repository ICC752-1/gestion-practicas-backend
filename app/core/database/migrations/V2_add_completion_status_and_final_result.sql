-- Backfill para bases existentes al introducir completion_status/final_result
-- y mantener coherencia con el cierre de prácticas de Sprint 11.7.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'enumCompletionStatus'
    ) THEN
        CREATE TYPE "enumCompletionStatus" AS ENUM (
            'not_started',
            'in_progress',
            'pending_evaluations',
            'pending_presentation',
            'finalized'
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'enumFinalResult'
    ) THEN
        CREATE TYPE "enumFinalResult" AS ENUM (
            'pending',
            'passed',
            'failed'
        );
    END IF;
END $$;

ALTER TABLE internship
ADD COLUMN IF NOT EXISTS completion_status "enumCompletionStatus";

ALTER TABLE internship
ADD COLUMN IF NOT EXISTS final_result "enumFinalResult";

UPDATE internship
SET completion_status = 'not_started'
WHERE completion_status IS NULL;

UPDATE internship
SET final_result = 'pending'
WHERE final_result IS NULL;

ALTER TABLE internship
ALTER COLUMN completion_status SET DEFAULT 'not_started';

ALTER TABLE internship
ALTER COLUMN final_result SET DEFAULT 'pending';

ALTER TABLE internship
ALTER COLUMN completion_status SET NOT NULL;

ALTER TABLE internship
ALTER COLUMN final_result SET NOT NULL;

-- Si una práctica ya fue anulada o rechazada, no corresponde marcarla como
-- finalizada por el nuevo flujo de cierre académico.
UPDATE internship AS i
SET
    completion_status = 'not_started',
    final_result = 'pending'
FROM currentstate AS cs
WHERE cs.id = i.status_id
  AND (
    i.is_cancelled IS TRUE
    OR cs.title = 'Rechazada'
  );
