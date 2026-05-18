"""Crea tablas de catálogo en Postgres si no existen. Ejecutar desde cafeAPI: python ensure_catalog_tables.py

También ejecuta ensure_recolector_propietario_finca_columns (ALTER idempotente).
"""
from database import Base, engine, ensure_recolector_propietario_finca_columns

# Registra todos los modelos en Base.metadata
from models import (  # noqa: F401
    persona,
    tipoDoc,
    propietario,
    recolector,
    reporte,
    pago,
    cat_tipo_insumo,
    cat_unidad_medida,
    cat_metodo_aplicacion,
)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ensure_recolector_propietario_finca_columns()
    print("Tablas verificadas/creadas (incl. cat_tipo_insumo, cat_unidad_medida, cat_metodo_aplicacion).")
