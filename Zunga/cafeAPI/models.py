from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from database import Base

class persona(Base):
    __tablename__ = "persona"
    documento_persona = Column(String, primary_key=True)
    nombre_persona = Column(String)
    edad_persona = Column(Integer)
    telefono_persona = Column(String)
    fk_tipo_documento = Column(Integer, ForeignKey("tipo_doc.id_doc"))

class tipoDoc(Base):
    __tablename__ = "tipo_doc"
    id_doc = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String)

class propietario(Base):
    __tablename__ = "propietario"
    id_propietario = Column(String, ForeignKey("persona.documento_persona"), primary_key=True)
    email_propietario = Column(String)
    estado_propietario = Column(Boolean)

class recolector(Base):
    __tablename__ = "recolector"
    id_recolector =  Column(String, ForeignKey("persona.documento_persona"), primary_key=True)
    fechainicio_recolector = Column(Date)
    fechafin_recolector = Column(Date)
    estado_recolector = Column(Boolean)
    diastrabajados_recolector = Column(Integer)
    fk_id_propietario = Column(String, ForeignKey("propietario.id_propietario"), nullable=True)
    fk_id_finca = Column(String, nullable=True)


class reporte(Base):
    __tablename__ = "reporte"
    id_reporte = Column(String, primary_key=True)
    fecha_reporte = Column(Date)
    totaltecoleccion_reporte = Column(Float)
    estado_reporte = Column(Boolean)
    fk_id_recolector = Column(String, ForeignKey("recolector.id_recolector"))

class pago(Base):
    __tablename__ = "pago"
    id_pago = Column(String, primary_key=True)
    fecha_pago = Column(Date)
    preciokilo_pago = Column(Float)
    estado_pago = Column(Boolean)
    monto_pago = Column(Float)
    metodo_pago = Column(String)
    fk_id_reporte = Column(String, ForeignKey("reporte.id_reporte"))


class cat_tipo_insumo(Base):
    __tablename__ = "cat_tipo_insumo"
    id_tipoinsumo = Column(String, primary_key=True)
    nombre_tipo = Column(String, nullable=False)


class cat_unidad_medida(Base):
    __tablename__ = "cat_unidad_medida"
    id_unidadmedida = Column(Integer, primary_key=True, autoincrement=True)
    nombre_unidadmedida = Column(String, nullable=False)


class cat_metodo_aplicacion(Base):
    __tablename__ = "cat_metodo_aplicacion"
    id_metodoaplicacion = Column(Integer, primary_key=True, autoincrement=True)
    nombre_metodoaplicacion = Column(String, nullable=False)

class usuario(Base):
    __tablename__ = "usuario"
    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    rol = Column(String, nullable=False) # 'admin', 'propietario', 'recolector'
    fk_persona = Column(String, ForeignKey("persona.documento_persona"), nullable=True)