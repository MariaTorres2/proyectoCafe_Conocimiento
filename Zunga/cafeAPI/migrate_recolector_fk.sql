-- Ejecutar contra la base bdcafe (Postgres).
-- Agrega vínculo recolector -> propietario y finca (id RDF).

ALTER TABLE recolector
  ADD COLUMN IF NOT EXISTS fk_id_propietario VARCHAR REFERENCES propietario(id_propietario),
  ADD COLUMN IF NOT EXISTS fk_id_finca VARCHAR;

COMMENT ON COLUMN recolector.fk_id_propietario IS 'Documento del propietario dueño del contrato';
COMMENT ON COLUMN recolector.fk_id_finca IS 'Id RDF de la finca asignada';
