
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from database import get_db, Base, ensure_recolector_propietario_finca_columns
from models import (
    persona,
    propietario,
    recolector,
    tipoDoc,
    reporte,
    pago,
    usuario,
    cat_tipo_insumo,
    cat_unidad_medida,
    cat_metodo_aplicacion,
)
from schemas import fincaModel, loteModel, insumoModel, compraModel, recoleccionModel, suministraInsumoModel, mantenimientoModel,eventoRecoleccionModel, inventarioModel
from schemas import personaModel, propietarioModel, recolectorModel, tipoDocModel, reporteModel, pagoModel, loginModel, usuarioModel
from schemas import catTipoInsumoModel, catUnidadMedidaCreateModel, catMetodoAplicacionCreateModel
from fastapi.middleware.cors import CORSMiddleware
import fuseki_client as fuseki
from fuseki_client import FusekiError


app = FastAPI(title="API Ontología RDF", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción pon la URL de tu Django
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
try:
    _triple_count = fuseki.count_triples()
    print(f"Fuseki conectado ({fuseki.FUSEKI_QUERY_URL}): {_triple_count} triples")
except FusekiError as e:
    print(f"ADVERTENCIA: no se pudo conectar a Fuseki: {e}")

ensure_recolector_propietario_finca_columns()

class reporteDiarioReq(BaseModel):
    id_recolector: str
    fecha: str  # YYYY-MM-DD


class liquidacionRecolectorReq(BaseModel):
    id_recolector: str
    precio_kilo: float
    propietario_doc: Optional[str] = None  # si viene, debe coincidir con fk_id_propietario del recolector


class DiaFinanzaManual(BaseModel):
    fecha: str  # YYYY-MM-DD
    kg_dia: float = 0
    precio_kilo: float = 0
    ausente: bool = False
    metodo_pago: Optional[str] = "Efectivo"


class GenerarPagoDiasReq(BaseModel):
    id_recolector: str
    dias: List[DiaFinanzaManual]
    propietario_doc: Optional[str] = None


def _rdf_propietario_de_finca(finca_id: str) -> Optional[str]:
    return fuseki.propietario_de_finca(finca_id)


def _kg_recolector_en_fecha(recolector_id: str, fecha_str: str) -> float:
    return fuseki.kg_recolector_en_fecha(recolector_id, fecha_str)


# Listar todas las clases ----------------------
@app.get("/clases")
def get_clases():
    query = """
        SELECT DISTINCT ?clase WHERE {
            ?clase a owl:Class .
            FILTER(!isBlank(?clase))
        }
    """
    resultados = fuseki.sparql_select(query)
    clases = [str(row.clase) for row in resultados]
    return {"total": len(clases), "clases": clases}


# Listar todas las propiedades ------------------
@app.get("/propiedades")
def get_propiedades():
    query = """
        SELECT DISTINCT ?prop WHERE {
            { ?prop a owl:ObjectProperty }
            UNION
            { ?prop a owl:DatatypeProperty }
        }
    """
    resultados = fuseki.sparql_select(query)
    props = [str(row.prop) for row in resultados]
    return {"total": len(props), "propiedades": props}


# Listar todos los individuos ----------------------
@app.get("/individuos")
def get_individuos():
    query = """
        SELECT DISTINCT ?ind ?tipo WHERE {
            ?ind a ?tipo .
            ?tipo a owl:Class .
            FILTER(!isBlank(?ind))
        }
    """
    resultados = fuseki.sparql_select(query)
    individuos = [{"individuo": str(row.ind), "tipo": str(row.tipo)} for row in resultados]
    return {"total": len(individuos), "individuos": individuos}




### Apache JENA -----------------------Ontologia

# --- Si existe el individuo
def existe_recurso(id_recurso: str) -> bool:
    return fuseki.resource_has_subject(id_recurso)

# ---Get individuo ----------
@app.get("/detalle/{id_recurso}", tags=["consultas"])
def get_detalle_individual(id_recurso: str):
    
    if not fuseki.resource_has_subject(id_recurso):
        raise HTTPException(
            status_code=404, 
            detail=f"El individuo '{id_recurso}' no existe en la base de datos."
        )

    detalles, relaciones = fuseki.get_resource_properties(id_recurso)

    return {
        "Id": id_recurso,
        "Datos": detalles,
        "Relaciones": relaciones
    }

# --- Get por clase ----------

@app.get("/detallesClase/{nombre_clase}", tags=["consultasClase"])
def get_individuosClase(nombre_clase: str):
  
    uri_clase = f"<{fuseki.CAFE_NS}{nombre_clase}>"
    
    query = f"""
        SELECT ?ind ?p ?o WHERE {{
            ?ind rdf:type ?clase .
            ?ind ?p ?o .
            FILTER(?clase = {uri_clase})
            FILTER(isLiteral(?o))
        }}
    """

    try:
        resultados = fuseki.sparql_select(query)
        respuesta = {}
        for row in resultados:
            ind_id = str(row.ind).split('/')[-1]
            propiedad = str(row.p).split('/')[-1]
            valor = row.o
            if ind_id not in respuesta:
                respuesta[ind_id] = {} 
            respuesta[ind_id][propiedad] = valor
        if not respuesta:
            return {"mensaje": f"No se encontraron individuos para  '{nombre_clase}'"}
        return {
            "Clase": nombre_clase,
            "Total de registros": len(respuesta),
            "Individuos": respuesta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {e}")

# --Eliminar por id individuo

@app.delete("/individuos/{id_recurso}", tags=["Eliminar"])
def eliminar_individuo(id_recurso: str):
    if not fuseki.resource_exists(id_recurso):
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró el individuo"
        )
    try:
        fuseki.delete_resource(id_recurso)
        return {
            "mensaje": f"El individuo ha sido eliminado.",
            "id_eliminado": id_recurso
        }
    except FusekiError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al intentar eliminar"
        )

# --Editar un individuo
@app.put("/corregirIndividuo/{id_recurso}", tags=["Editar"])
def editar_individuo(id_recurso: str, nuevos_datos: dict):
    if not fuseki.resource_has_subject(id_recurso):
        raise HTTPException(
            status_code=404, 
            detail=f"No se puede editar"
        )
    
    try:
        tipo_original = fuseki.get_rdf_type(id_recurso)
        fuseki.delete_literal_properties(id_recurso)
        fuseki.set_literal_properties(id_recurso, nuevos_datos)
        if tipo_original:
            fuseki.restore_rdf_type(id_recurso, tipo_original)
        return {
            "mensaje": f"Individuo '{id_recurso}' actualizado correctamente.",
            "datos_actualizados": nuevos_datos
        }
    except FusekiError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=500, 
            detail=f"Error durante la edición"
        )

# -- Guardar -----------------

def guardar_rdf(id_uri, tipo_clase, id_numero, datos_restantes, relaciones_dict=None):
    try:
        fuseki.guardar_individuo(
            str(id_uri),
            str(tipo_clase),
            int(id_numero),
            datos_restantes or {},
            relaciones_dict,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"El individuo ya existe.")
    except FusekiError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Crear un individuo RDF genérico por clase
@app.post("/individuos/{tipo_clase}", tags=["Estructura"])
def crear_individuo_generico(tipo_clase: str, body: dict = Body(...)):
    """
    body esperado:
      - id_uri: str (obligatorio)
      - id_numeric: int (obligatorio)
      - datos: dict (propiedades literales)
      - relaciones: dict (propiedades -> id_destino)
    """
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body inválido")
    id_uri = body.get("id_uri") or body.get("id") or body.get("id_recurso")
    id_numeric = body.get("id_numeric")
    datos = body.get("datos") or {}
    relaciones = body.get("relaciones") or {}
    if not id_uri or id_numeric is None:
        raise HTTPException(status_code=400, detail="id_uri e id_numeric son obligatorios")
    if not isinstance(datos, dict) or not isinstance(relaciones, dict):
        raise HTTPException(status_code=400, detail="datos/relaciones deben ser dict")
    guardar_rdf(str(id_uri), str(tipo_clase), int(id_numeric), datos, relaciones)
    return {"status": "creado", "id": str(id_uri), "clase": str(tipo_clase)}

# -- Post por clase------------------

# Finca
@app.post("/fincas", tags=["Estructura"])
def insert_finca(data: fincaModel, db: Session = Depends(get_db)):

    propietario_sql = db.query(propietario).filter(
        propietario.id_propietario == data.FK_idPropietario
    ).first()
    if not propietario_sql:
        raise HTTPException(
            status_code=404, 
            detail="Propietario no existe"
        )

    datos = {
        "nombre": data.nombre, 
        "direccion": data.direccion, 
        "area": data.area, 
        "altitud": data.altitud,
        "fk_idPropietario": propietario_sql.id_propietario  
    }
    guardar_rdf(data.id_finca, "finca", data.id_numeric, datos)
    for l_id in data.lotes:
        fuseki.add_object_triple(data.id_finca, "contieneLote", l_id)
    for c_id in data.compras:
        fuseki.add_object_triple(data.id_finca, "realizaCompra", c_id)
    return {"status": "Finca registrada"}

#Lote
@app.post("/lotes", tags=["Estructura"])
def insert_lote(data: loteModel):
    datos= {
        "nombre": data.nombre, 
        "area": data.area, 
        "cantidad": data.cantidad, 
        "estado": data.estado
    } 
    guardar_rdf(data.id_lote, "lote", data.id_numeric, datos)
    for e_id in data.eventosRecoleccion:
        fuseki.add_object_triple(data.id_lote, "estableceRecoleccion", e_id)
    for s_id in data.suministros:
        fuseki.add_object_triple(data.id_lote, "seAbastecePor", s_id)
    for m_id in data.mantenimientos:
        fuseki.add_object_triple(data.id_lote, "tieneMantenimiento", m_id)
    return {"status": "Lote registrado"}

@app.post("/compras", tags=["Estructura"])
def insert_compra(data: compraModel):
    datos = {"fecha": data.fecha, "cantidad": data.cantidad, "precio": data.precio, "estado": data.estado}
    relaciones = {"incluyeInsumo": data.id_insumo, "esCompraDe": data.id_finca}
    guardar_rdf(data.id_compra, "compra", data.id_numeric, datos, relaciones)
    return {"status": "Compra registrada"}

#Insumos
@app.post("/insumos", tags=["Estructura"])
def insert_insumo(data: insumoModel):
    datos = {
        "nombre": data.nombre, 
        "precio": data.precio, 
        "tipo": data.tipo, 
        "estado": data.estado,
        "unidadMedida": data.unidadMedida,
        "metodoAplicacion": data.metodoAplicacion,
    }
    datos = {k: v for k, v in datos.items() if v not in (None, "")}
    guardar_rdf(data.id_insumo, "insumo", data.id_numeric, datos)
    for c_id in getattr(data, 'compras', []):
        fuseki.add_object_triple(data.id_insumo, "esAdquiridoPor", c_id)
    for s_id in getattr(data, 'suministrosVinculados', []):
        fuseki.add_object_triple(data.id_insumo, "permiteLa", s_id)
    return {"status": "Insumo registrado"}

#Inventario
@app.post("/inventarios", tags=["Estructura"])
def insert_inventario(data: inventarioModel):
    datos = {
        "cantidad": data.cantidad,
        "fecha": data.fecha,
        "unidadMedida": data.unidadMedida
    }
    relaciones = {"contieneInsumo": data.id_insumo}
    guardar_rdf(data.id_inventario, "inventario", data.id_numeric, datos, relaciones)
    return {"status": "Inventario registrado"}

#Suministros
@app.post("/suministros", tags=["Estructura"])
def insert_suministro(data: suministraInsumoModel):
    datos = {"fecha": data.fecha, "cantidad": data.cantidad, "estado": data.estado}
    relaciones = {
        "requiereA": data.id_insumo, 
        "seaplicaEn": data.id_lote  
    }
    guardar_rdf(data.id_suministro, "suministroInsumo", data.id_numeric, datos, relaciones)
    return {"status": "Suministro registrado"}

#Mantenimiento
@app.post("/mantenimientos", tags=["Estructura"])
def insert_mantenimiento(data: mantenimientoModel):
    datos = {"fecha": data.fecha, "tipo": data.tipo}
    guardar_rdf(data.id_mantenimiento, "mantenimiento", data.id_numeric, datos)
    return {"status": "Mantenimiento registrado"}


#Recoleccion
@app.post("/recolecciones", tags=["Estructura"])
def insert_recoleccion(data: recoleccionModel, db: Session = Depends(get_db)):
    recolector_sql = db.query(recolector).filter(
        recolector.id_recolector == data.FK_idRecolector
    ).first()

    if not recolector_sql:
        raise HTTPException(
            status_code=404, 
            detail="El recolector no existe"
        )
    # Validar rango de contrato del recolector
    try:
        fecha_rec = datetime.fromisoformat(str(data.fecha)[:10]).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha de recolección inválida (use YYYY-MM-DD)")
    inicio = recolector_sql.fechainicio_recolector
    fin = recolector_sql.fechafin_recolector or date.today()
    if fecha_rec < inicio or fecha_rec > fin:
        raise HTTPException(
            status_code=400,
            detail=f"Fecha fuera de rango. Debe estar entre {inicio.isoformat()} y {fin.isoformat()}",
        )
    datos = {
        "fecha": data.fecha,
        "fk_idRecolector": recolector_sql.id_recolector  
    }
    guardar_rdf(data.id_recoleccion, "recoleccion", data.id_numeric, datos)
    return {"status": "Recoleccion registrada"}

#Evento Recoleccion
@app.post("/eventosRecoleccion", tags=["Estructura"])
def insert_evento_recoleccion(data: eventoRecoleccionModel):
    datos = {
        "cantidad": data.cantidad
    }
    relaciones = {
        "ocurreEn": data.id_lote,
        "generaRecoleccion": data.id_recoleccion
    }
    guardar_rdf(data.id_evento, "eventoRecoleccion", data.id_numeric, datos, relaciones)
    return {"status": "Evento de recoleccion registrado"}

### Postgres -----------------------Bd

# Get un registro
@app.get("/consultarRegistro/{nombre_tabla}/{id_registro}", tags=["consultas"])
def get_registro(nombre_tabla: str, id_registro: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="La tabla no existe")
    pk_name = tabla.primary_key.columns.values()[0].name
    query = text(f"SELECT * FROM {tabla.name} WHERE {pk_name} = :id")
    resultado = db.execute(query, {"id": id_registro}).mappings().first()

    if not resultado:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró registro con ID {id_registro} en la tabla {nombre_tabla}"
        )

    return resultado

# Get todos los registros de una tabla

@app.get("/detallesT/{nombre_tabla}", tags=["consultasClase"])
def get_todos(nombre_tabla: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())

    if tabla is None:
        raise HTTPException(
            status_code=404, 
            detail="La tabla no existe"
        )
    query = text(f"SELECT * FROM {tabla.name}")
    resultados = db.execute(query).mappings().all()
    return resultados


# Crear un registro en cualquier tabla Postgres registrada en SQLAlchemy
@app.post("/registros/{nombre_tabla}", tags=["Estructura"])
def crear_registro(nombre_tabla: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get((nombre_tabla or "").lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Payload inválido")

    cols = {c.name for c in tabla.columns}
    data = {k: v for k, v in payload.items() if k in cols}
    if not data:
        raise HTTPException(status_code=400, detail="No hay campos válidos para insertar")

    pk_col = list(tabla.primary_key.columns)[0]
    keys = ", ".join(data.keys())
    vals = ", ".join([f":{k}" for k in data.keys()])
    q = text(f"INSERT INTO {tabla.name} ({keys}) VALUES ({vals}) RETURNING {pk_col.name}")
    def _reset_serial_sequence_if_any():
        # Corrige secuencia (caso típico: SERIAL desincronizado → duplicate key en PK)
        try:
            db.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(:tname, :pk),
                        COALESCE((SELECT MAX({pk_col.name}) FROM {tabla.name}), 0) + 1,
                        false
                    )
                    """
                ),
                {"tname": tabla.name, "pk": pk_col.name},
            )
            db.commit()
        except Exception:
            db.rollback()

    try:
        new_id = db.execute(q, data).scalar()
        db.commit()
    except Exception as e:
        # Retry 1 vez si parece PK duplicada por secuencia desincronizada
        msg = str(e)
        db.rollback()
        if (f"{tabla.name}_pkey" in msg) and ("UniqueViolation" in msg or "llave duplicada" in msg or "duplicate key" in msg):
            _reset_serial_sequence_if_any()
            try:
                new_id = db.execute(q, data).scalar()
                db.commit()
            except Exception as e2:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Error al insertar: {str(e2)}")
        else:
            raise HTTPException(status_code=400, detail=f"Error al insertar: {msg}")
    return {"status": "creado", "id": new_id}


def _cascade_delete_recolector_db(db: Session, rid: str) -> None:
    """Quita pagos y reportes ligados al recolector y luego la fila recolector."""
    db.execute(
        text(
            "DELETE FROM pago WHERE fk_id_reporte IN "
            "(SELECT id_reporte FROM reporte WHERE fk_id_recolector = :rid)"
        ),
        {"rid": rid},
    )
    db.execute(text("DELETE FROM reporte WHERE fk_id_recolector = :rid"), {"rid": rid})
    db.execute(text("DELETE FROM recolector WHERE id_recolector = :rid"), {"rid": rid})


def _recolector_tabla_tiene_columnas_propietario_finca(db: Session) -> bool:
    """True si existe migrate_recolector_fk.sql aplicado (columnas en Postgres)."""
    try:
        n = db.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'recolector'
                  AND column_name IN ('fk_id_propietario', 'fk_id_finca')
                """
            )
        ).scalar()
        return int(n or 0) >= 2
    except Exception:
        return False


def _liberar_recolectores_de_propietario(db: Session, doc_propietario: str) -> None:
    if not _recolector_tabla_tiene_columnas_propietario_finca(db):
        return
    db.execute(
        text(
            "UPDATE recolector SET fk_id_propietario = NULL, fk_id_finca = NULL "
            "WHERE fk_id_propietario = :doc"
        ),
        {"doc": doc_propietario},
    )


# Eliminar un registro en cascada
@app.delete("/registros/{nombre_tabla}/{id_registro}", tags=["Eliminar"])
def eliminar_registro(nombre_tabla: str, id_registro: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get((nombre_tabla or "").lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    pk_column = list(tabla.primary_key.columns)[0].name

    if tabla.name == "persona":
        db.execute(text("DELETE FROM usuario WHERE fk_persona = :doc"), {"doc": id_registro})
        _liberar_recolectores_de_propietario(db, id_registro)
        db.execute(text("DELETE FROM propietario WHERE id_propietario = :doc"), {"doc": id_registro})
        _cascade_delete_recolector_db(db, id_registro)
    elif tabla.name == "propietario":
        _liberar_recolectores_de_propietario(db, id_registro)
    elif tabla.name == "recolector":
        _cascade_delete_recolector_db(db, id_registro)
        db.commit()
        if fuseki.resource_exists(id_registro):
            fuseki.delete_resource(id_registro)
        return {"status": "Eliminacion realizada"}

    query = text(f"DELETE FROM {tabla.name} WHERE {pk_column} = :id")
    result = db.execute(query, {"id": id_registro})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="El registro no existe en Postgres")

    if fuseki.resource_exists(id_registro):
        fuseki.delete_resource(id_registro)
    return {"status": "Eliminacion realizada"}

# Editar un registro
@app.patch("/corregirRegistro/{nombre_tabla}/{id_registro}", tags=["Editar"])
def editar_registro(
    nombre_tabla: str, 
    id_registro: str, 
    actualizaciones: dict = Body(...), 
    db: Session = Depends(get_db)
):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    pk_column = tabla.primary_key.columns.values()[0].name

    # Recolector: recalcular días trabajados cuando cambian fechas (campo no editable)
    if tabla.name.lower() == "recolector" and isinstance(actualizaciones, dict):
        if "diastrabajados_recolector" in actualizaciones:
            actualizaciones.pop("diastrabajados_recolector", None)
        if "fechainicio_recolector" in actualizaciones or "fechafin_recolector" in actualizaciones:
            def _to_date(value):
                if value in (None, ""):
                    return None
                if isinstance(value, date):
                    return value
                return datetime.fromisoformat(str(value).strip()[:10]).date()

            row = db.execute(
                text(f"SELECT fechainicio_recolector, fechafin_recolector FROM {tabla.name} WHERE {pk_column} = :id"),
                {"id": id_registro},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="No existe el registro")
            try:
                fi = _to_date(actualizaciones.get("fechainicio_recolector")) or _to_date(row.get("fechainicio_recolector"))
                ff = _to_date(actualizaciones.get("fechafin_recolector")) or _to_date(row.get("fechafin_recolector")) or date.today()
                dias = (ff - fi).days
            except Exception:
                raise HTTPException(status_code=400, detail="Fechas inválidas")
            if dias < 0:
                raise HTTPException(status_code=400, detail="fechafin_recolector no puede ser menor a fechainicio_recolector")
            actualizaciones["diastrabajados_recolector"] = dias

    campos_set = ", ".join([f"{campo} = :{campo}" for campo in actualizaciones.keys()])
    
    if not campos_set:
        raise HTTPException(status_code=400, detail="No hay campos")

    query = text(f"UPDATE {tabla.name} SET {campos_set} WHERE {pk_column} = :id_pk")
    parametros = {**actualizaciones, "id_pk": id_registro}

    result = db.execute(query, parametros)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="No existe el registro")
    
    if fuseki.resource_has_subject(id_registro):
        for campo, nuevo_valor in actualizaciones.items():
            fuseki.set_predicate_literal(id_registro, campo, nuevo_valor)
    return {
        "status": "Actualización realizada",
        "campos_modificados": list(actualizaciones.keys())
    }

# --- Auth ---
@app.post("/login", tags=["Auth"])
def login(data: loginModel, db: Session = Depends(get_db)):
    user = db.query(usuario).filter(usuario.username == data.username).first()
    if not user or user.password != data.password:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {
        "status": "success",
        "username": user.username,
        "rol": user.rol,
        "fk_persona": user.fk_persona
    }

@app.post("/usuarios", tags=["Auth"])
def register_user(data: usuarioModel, db: Session = Depends(get_db)):
    if db.query(usuario).filter(usuario.username == data.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    rol = (data.rol or "").strip().lower()
    if rol not in ("admin", "propietario", "recolector"):
        raise HTTPException(status_code=400, detail="Rol inválido. Use: admin, propietario, recolector")
    
    nuevo_usuario = usuario(
        username=data.username,
        password=data.password,
        rol=rol,
        fk_persona=data.fk_persona
    )
    db.add(nuevo_usuario)
    db.commit()
    return {"mensaje": "Usuario registrado"}

# ---- Post-----------

#Persona
@app.post("/personas", tags=["Estructura"])
def insert_persona(data: personaModel, db: Session = Depends(get_db)):
    nueva_persona = persona(
        documento_persona=data.documento_persona,
        nombre_persona=data.nombre_persona,
        edad_persona=data.edad_persona,
        telefono_persona=data.telefono_persona,
        fk_tipo_documento=data.fk_tipo_documento
    )
    db.add(nueva_persona)
    db.commit()
    db.refresh(nueva_persona)
    return {"mensaje": "Persona registrada"}

#Tipo doc
@app.post("/tipoDocumento", tags=["Estructura"])
def insert_tipo_documento(data: tipoDocModel, db: Session = Depends(get_db)):
        nuevo_tipo = tipoDoc(
            id_doc=data.id_doc,
           tipo=data.tipo,
        )
        db.add(nuevo_tipo)
        db.commit()
        db.refresh(nuevo_tipo)
        return {
            "mensaje": "Tipo de documento registrado"
        }

#Propietario
@app.post("/propietarios", tags=["Estructura"])
def insert_propietario(data: propietarioModel, db: Session = Depends(get_db)):
    nuevo_propietario = propietario(
        id_propietario=data.id_propietario,
        email_propietario=data.email_propietario,
        estado_propietario=data.estado_propietario
    )
    db.add(nuevo_propietario)
    db.commit()
    return {"mensaje": "Propietario registrado"}

#Recolector
@app.post("/recolectores", tags=["Estructura"])
def insert_recolector(data: recolectorModel, db: Session = Depends(get_db)):
    # Los días trabajados se calculan a partir de las fechas (no editable por UI)
    fin = data.fechafin_recolector or date.today()
    dias = (fin - data.fechainicio_recolector).days
    if dias < 0:
        raise HTTPException(status_code=400, detail="fechafin_recolector no puede ser menor a fechainicio_recolector")

    fk_prop = (data.fk_id_propietario or "").strip() or None
    fk_fin = (data.fk_id_finca or "").strip() or None

    if fk_fin:
        prop_de_finca = _rdf_propietario_de_finca(fk_fin)
        if prop_de_finca is None:
            raise HTTPException(status_code=404, detail="La finca no existe en RDF")
        if fk_prop and prop_de_finca != fk_prop:
            raise HTTPException(status_code=400, detail="La finca no pertenece al propietario indicado")
        if not fk_prop:
            fk_prop = prop_de_finca

    tiene_columnas_fk = _recolector_tabla_tiene_columnas_propietario_finca(db)
    aviso = None
    if not tiene_columnas_fk and (fk_fin or fk_prop):
        aviso = (
            "La tabla recolector en Postgres no tiene aún las columnas fk_id_propietario/fk_id_finca. "
            "Ejecute cafeAPI/migrate_recolector_fk.sql en bdcafe. El recolector se guardó sin esos vínculos."
        )
        fk_prop = None
        fk_fin = None

    if tiene_columnas_fk:
        nuevo_recolector = recolector(
            id_recolector=data.id_recolector,
            fechainicio_recolector=data.fechainicio_recolector,
            fechafin_recolector=data.fechafin_recolector,
            estado_recolector=data.estado_recolector,
            diastrabajados_recolector=dias,
            fk_id_propietario=fk_prop,
            fk_id_finca=fk_fin,
        )
        db.add(nuevo_recolector)
    else:
        db.execute(
            text(
                """
                INSERT INTO recolector (
                    id_recolector, fechainicio_recolector, fechafin_recolector,
                    estado_recolector, diastrabajados_recolector
                ) VALUES (
                    :id, :fi, :ff, :est, :dias
                )
                """
            ),
            {
                "id": data.id_recolector,
                "fi": data.fechainicio_recolector,
                "ff": data.fechafin_recolector,
                "est": data.estado_recolector,
                "dias": dias,
            },
        )
    db.commit()
    out: dict = {"mensaje": "Recolector registrado"}
    if aviso:
        out["aviso"] = aviso
    return out

#Reporte
@app.post("/reportes", tags=["Estructura"])
def insert_reporte(data: reporteModel, db: Session = Depends(get_db)):
        nuevo_reporte = reporte(
            id_reporte=data.id_reporte,
            fecha_reporte=data.fecha_reporte,
            totaltecoleccion_reporte=data.totaltecoleccion_reporte,
            estado_reporte=data.estado_reporte,
            fk_id_recolector=data.fk_id_recolector
        )
        db.add(nuevo_reporte)
        db.commit()
        db.refresh(nuevo_reporte)
        return {
            "mensaje": "Reporte registrado"
        }

#Pago
@app.post("/pagos", tags=["Estructura"])
def insert_pago(data: pagoModel, db: Session = Depends(get_db)):
        nuevo_pago = pago(
            id_pago=data.id_pago,
            fecha_pago=data.fecha_pago,
            preciokilo_pago=data.preciokilo_pago,
            estado_pago=data.estado_pago,
            monto_pago=data.monto_pago,
            metodo_pago=data.metodo_pago,
            fk_id_reporte=data.fk_id_reporte
        )
        db.add(nuevo_pago)
        db.commit()
        db.refresh(nuevo_pago)
        return {
            "mensaje": "Pago registrado"
        }


@app.get("/finanzas/kg_sugerido", tags=["Finanzas"])
def finanzas_kg_sugerido(
    id_recolector: str,
    fecha: str,
    propietario_doc: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Kg del día según RDF (solo lectura), sin crear reporte."""
    rid = (id_recolector or "").strip()
    fs = (fecha or "").strip()[:10]
    if not rid or not fs:
        raise HTTPException(status_code=400, detail="id_recolector y fecha son obligatorios")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if propietario_doc:
        pd = str(propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")
    try:
        fd = datetime.fromisoformat(fs).date()
    except Exception:
        raise HTTPException(status_code=400, detail="fecha inválida (YYYY-MM-DD)")
    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fd < inicio or fd > fin:
        raise HTTPException(
            status_code=400,
            detail=f"Fecha fuera del contrato ({inicio.isoformat()} — {fin.isoformat()})",
        )
    kg = float(_kg_recolector_en_fecha(rid, fs))
    return {"id_recolector": rid, "fecha": fs, "kg_sugerido": kg}


@app.post("/finanzas/generar_pago", tags=["Finanzas"])
def finanzas_generar_pago(data: GenerarPagoDiasReq, db: Session = Depends(get_db)):
    """
    Registra reporte + pago por cada día trabajado (kg × precio/kg).
    Días marcados ausente eliminan reporte/pago de ese día si existían.
    """
    rid = (data.id_recolector or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="id_recolector es obligatorio")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if data.propietario_doc:
        pd = str(data.propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")

    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fin < inicio:
        raise HTTPException(status_code=400, detail="Rango de contrato inválido")

    if not data.dias:
        raise HTTPException(status_code=400, detail="Debe enviar al menos un día para liquidar")

    fechas_vistas = set()
    dias_normalizados = []
    dias_omitidos = []
    detalle = []
    total_kg = 0.0
    total_monto = 0.0
    pagos_n = 0

    for d in data.dias:
        fs = (d.fecha or "").strip()[:10]
        if fs in fechas_vistas:
            raise HTTPException(status_code=400, detail=f"Fecha duplicada: {fs}")
        fechas_vistas.add(fs)
        try:
            fd = datetime.fromisoformat(fs).date()
        except Exception:
            raise HTTPException(status_code=400, detail=f"fecha inválida: {d.fecha}")
        if fd < inicio or fd > fin:
            raise HTTPException(status_code=400, detail=f"La fecha {fs} está fuera del contrato")

        reporte_id = f"RD_{rid}_{fs}"
        id_pago = f"PAGO_MAN_{rid}_{fs}"
        pago_existente = db.query(pago).filter(pago.fk_id_reporte == reporte_id).first()
        if not pago_existente:
            pago_existente = db.query(pago).filter(pago.id_pago == id_pago).first()
        if pago_existente:
            dias_omitidos.append({"fecha": fs, "motivo": "Ya se reportó pago para este día"})
            continue

        if d.ausente:
            dias_normalizados.append(
                {
                    "fecha": fs,
                    "fecha_date": fd,
                    "reporte_id": reporte_id,
                    "id_pago": id_pago,
                    "ausente": True,
                    "kg": 0.0,
                    "precio_kilo": 0.0,
                }
            )
            continue

        metodo_pago = (d.metodo_pago or "Efectivo").strip()
        if metodo_pago not in ("Efectivo", "Transferencia", "Tarjeta"):
            raise HTTPException(status_code=400, detail=f"Método de pago inválido para el día {fs}")
        kg = float(d.kg_dia or 0)
        pk = float(d.precio_kilo or 0)
        if pk < 0:
            raise HTTPException(status_code=400, detail=f"precio_kilo no puede ser negativo ({fs})")
        if kg < 0:
            raise HTTPException(status_code=400, detail=f"kg_dia no puede ser negativo ({fs})")
        dias_normalizados.append(
            {
                "fecha": fs,
                "fecha_date": fd,
                "reporte_id": reporte_id,
                "id_pago": id_pago,
                "ausente": False,
                "kg": kg,
                "precio_kilo": pk,
                "metodo_pago": metodo_pago,
            }
        )

    if not dias_normalizados:
        raise HTTPException(status_code=400, detail="Todos los días enviados ya fueron reportados")

    for d in dias_normalizados:
        fs = d["fecha"]
        fd = d["fecha_date"]
        reporte_id = d["reporte_id"]

        if d["ausente"]:
            db.query(pago).filter(pago.fk_id_reporte == reporte_id).delete(synchronize_session=False)
            db.query(reporte).filter(reporte.id_reporte == reporte_id).delete(synchronize_session=False)
            detalle.append({"fecha": fs, "ausente": True, "kg_dia": 0.0, "precio_kilo": 0.0, "monto_dia": 0.0})
            continue

        kg = d["kg"]
        pk = d["precio_kilo"]
        monto = kg * pk
        total_kg += kg
        total_monto += monto

        rep = db.query(reporte).filter(reporte.id_reporte == reporte_id).first()
        if rep:
            rep.fecha_reporte = fd
            rep.totaltecoleccion_reporte = float(kg)
            rep.estado_reporte = True
            rep.fk_id_recolector = rid
        else:
            db.add(
                reporte(
                    id_reporte=reporte_id,
                    fecha_reporte=fd,
                    totaltecoleccion_reporte=float(kg),
                    estado_reporte=True,
                    fk_id_recolector=rid,
                )
            )

        db.flush()
        db.add(
            pago(
                id_pago=d["id_pago"],
                fecha_pago=fd,
                preciokilo_pago=float(pk),
                estado_pago=True,
                monto_pago=float(monto),
                metodo_pago=d["metodo_pago"],
                fk_id_reporte=reporte_id,
            )
        )
        pagos_n += 1
        detalle.append({"fecha": fs, "ausente": False, "kg_dia": kg, "precio_kilo": pk, "monto_dia": monto, "metodo_pago": d["metodo_pago"]})

    db.commit()
    mensaje = "Liquidación registrada"
    if dias_omitidos:
        mensaje = f"Liquidación registrada. Se omitieron {len(dias_omitidos)} día(s) ya reportado(s)."
    return {
        "mensaje": mensaje,
        "id_recolector": rid,
        "total_kg": total_kg,
        "total_monto": total_monto,
        "pagos_registrados": pagos_n,
        "dias_omitidos": dias_omitidos,
        "detalle": detalle,
    }


@app.post("/reportes/diario", tags=["Reporte"])
def generar_reporte_diario(data: reporteDiarioReq, db: Session = Depends(get_db)):
    recolector_id = (data.id_recolector or "").strip()
    fecha_str = (data.fecha or "").strip()[:10]
    if not recolector_id or not fecha_str:
        raise HTTPException(status_code=400, detail="id_recolector y fecha son obligatorios")
    try:
        fecha = datetime.fromisoformat(fecha_str).date()
    except Exception:
        raise HTTPException(status_code=400, detail="fecha inválida (use YYYY-MM-DD)")

    rec_sql = db.query(recolector).filter(recolector.id_recolector == recolector_id).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fecha < inicio or fecha > fin:
        raise HTTPException(status_code=400, detail=f"Fecha fuera de rango ({inicio.isoformat()} - {fin.isoformat()})")

    total_cantidad = int(fuseki.kg_recolector_en_fecha(recolector_id, fecha_str))

    reporte_id = f"RD_{recolector_id}_{fecha_str}"
    rep = db.query(reporte).filter(reporte.id_reporte == reporte_id).first()
    if not rep:
        rep = reporte(
            id_reporte=reporte_id,
            fecha_reporte=fecha,
            totaltecoleccion_reporte=float(total_cantidad),
            estado_reporte=True,
            fk_id_recolector=recolector_id,
        )
        db.add(rep)
    else:
        rep.fecha_reporte = fecha
        rep.totaltecoleccion_reporte = float(total_cantidad)
        rep.estado_reporte = True
        rep.fk_id_recolector = recolector_id
    db.commit()

    pagado = 0.0
    try:
        pagos = db.query(pago).filter(pago.fk_id_reporte == reporte_id).all()
        for p in pagos:
            pagado += float(p.monto_pago or 0)
    except Exception:
        pagado = 0.0

    return {
        "id_reporte": reporte_id,
        "fecha_reporte": fecha_str,
        "fk_id_recolector": recolector_id,
        "total_recolectado": total_cantidad,
        "total_pagado": pagado,
    }


@app.post("/liquidacion/recolector", tags=["Reporte"])
def liquidacion_recolector(data: liquidacionRecolectorReq, db: Session = Depends(get_db)):
    rid = (data.id_recolector or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="id_recolector es obligatorio")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if data.propietario_doc:
        pd = str(data.propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")

    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fin < inicio:
        raise HTTPException(status_code=400, detail="Rango de contrato inválido")

    pk = float(data.precio_kilo or 0)
    dias_out = []
    total_kg = 0.0
    total_monto = 0.0
    d = inicio
    while d <= fin:
        fs = d.isoformat()
        kg = _kg_recolector_en_fecha(rid, fs)
        monto = kg * pk
        dias_out.append({"fecha": fs, "kg_dia": kg, "monto_dia": monto})
        total_kg += kg
        total_monto += monto
        d += timedelta(days=1)

    return {
        "id_recolector": rid,
        "precio_kilo": pk,
        "dias": dias_out,
        "total_kg": total_kg,
        "total_monto": total_monto,
    }


# --- Catálogos Postgres (tipo insumo, unidad medida, método aplicación) ---
@app.post("/catalogo/tipoInsumo", tags=["Catalogo"])
def catalogo_tipo_insumo_post(data: catTipoInsumoModel, db: Session = Depends(get_db)):
    if not (data.id_tipoinsumo or "").strip() or not (data.nombre_tipo or "").strip():
        raise HTTPException(status_code=400, detail="id_tipoinsumo y nombre_tipo son obligatorios")
    if db.query(cat_tipo_insumo).filter(cat_tipo_insumo.id_tipoinsumo == data.id_tipoinsumo).first():
        raise HTTPException(status_code=400, detail="Ya existe un tipo de insumo con ese id")
    row = cat_tipo_insumo(id_tipoinsumo=data.id_tipoinsumo, nombre_tipo=data.nombre_tipo)
    db.add(row)
    db.commit()
    return {
        "mensaje": "Tipo de insumo registrado",
        "data": {"id_tipoinsumo": data.id_tipoinsumo, "nombre_tipo": data.nombre_tipo},
    }


@app.post("/catalogo/unidadMedida", tags=["Catalogo"])
def catalogo_unidad_medida_post(data: catUnidadMedidaCreateModel, db: Session = Depends(get_db)):
    nombre = (data.nombre_unidadmedida or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="nombre_unidadmedida es obligatorio")
    row = cat_unidad_medida(nombre_unidadmedida=nombre)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "mensaje": "Unidad registrada",
        "data": {
            "id_unidadmedida": row.id_unidadmedida,
            "nombre_unidadmedida": row.nombre_unidadmedida,
        },
    }


@app.post("/catalogo/metodoAplicacion", tags=["Catalogo"])
def catalogo_metodo_aplicacion_post(data: catMetodoAplicacionCreateModel, db: Session = Depends(get_db)):
    nombre = (data.nombre_metodoaplicacion or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="nombre_metodoaplicacion es obligatorio")
    usados = {
        row[0]
        for row in db.query(cat_metodo_aplicacion.id_metodoaplicacion)
        .order_by(cat_metodo_aplicacion.id_metodoaplicacion)
        .all()
    }
    siguiente_id = 1
    while siguiente_id in usados:
        siguiente_id += 1
    row = cat_metodo_aplicacion(
        id_metodoaplicacion=siguiente_id,
        nombre_metodoaplicacion=nombre,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "mensaje": "Método registrado",
        "data": {
            "id_metodoaplicacion": row.id_metodoaplicacion,
            "nombre_metodoaplicacion": row.nombre_metodoaplicacion,
        },
    }