from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker



URL_POSTGRES = "postgresql://postgres:admin@localhost:5432/bdcafe"

engine = create_engine(
    URL_POSTGRES, 
    connect_args={"options": "-c client_encoding=utf8"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_recolector_propietario_finca_columns() -> None:
    """ALTER idempotente: alinea Postgres con los modelos actuales."""
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    ALTER TABLE recolector
                      ADD COLUMN IF NOT EXISTS fk_id_propietario VARCHAR REFERENCES propietario(id_propietario),
                      ADD COLUMN IF NOT EXISTS fk_id_finca VARCHAR;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    DO $$
                    DECLARE
                        fk record;
                    BEGIN
                        FOR fk IN
                            SELECT conname
                            FROM pg_constraint
                            WHERE conrelid = 'pago'::regclass
                              AND contype = 'f'
                              AND EXISTS (
                                  SELECT 1
                                  FROM unnest(conkey) AS colnum
                                  WHERE colnum = (
                                      SELECT attnum
                                      FROM pg_attribute
                                      WHERE attrelid = 'pago'::regclass
                                        AND attname = 'fk_id_reporte'
                                  )
                              )
                        LOOP
                            EXECUTE format('ALTER TABLE pago DROP CONSTRAINT %I', fk.conname);
                        END LOOP;
                    END $$;

                    ALTER TABLE reporte ALTER COLUMN id_reporte DROP DEFAULT;
                    ALTER TABLE pago ALTER COLUMN id_pago DROP DEFAULT;

                    ALTER TABLE reporte
                      ALTER COLUMN id_reporte TYPE VARCHAR USING id_reporte::VARCHAR,
                      ALTER COLUMN estado_reporte TYPE BOOLEAN USING
                        CASE
                          WHEN LOWER(estado_reporte::TEXT) IN ('true', 't', '1', 'si', 'sí', 'activo', 'activa') THEN TRUE
                          WHEN LOWER(estado_reporte::TEXT) IN ('false', 'f', '0', 'no', 'inactivo', 'inactiva') THEN FALSE
                          ELSE FALSE
                        END;

                    ALTER TABLE pago
                      ALTER COLUMN id_pago TYPE VARCHAR USING id_pago::VARCHAR,
                      ALTER COLUMN fk_id_reporte TYPE VARCHAR USING fk_id_reporte::VARCHAR,
                      ALTER COLUMN estado_pago TYPE BOOLEAN USING
                        CASE
                          WHEN LOWER(estado_pago::TEXT) IN ('true', 't', '1', 'si', 'sí', 'activo', 'activa') THEN TRUE
                          WHEN LOWER(estado_pago::TEXT) IN ('false', 'f', '0', 'no', 'inactivo', 'inactiva') THEN FALSE
                          ELSE FALSE
                        END;

                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'pago_fk_id_reporte_fkey'
                              AND conrelid = 'pago'::regclass
                        ) THEN
                            ALTER TABLE pago
                              ADD CONSTRAINT pago_fk_id_reporte_fkey
                              FOREIGN KEY (fk_id_reporte) REFERENCES reporte(id_reporte)
                              ON DELETE CASCADE;
                        END IF;
                    END $$;
                    """
                )
            )
    except Exception as ex:
        print(f"[bdcafe] ensure_recolector_propietario_finca_columns: {ex}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()