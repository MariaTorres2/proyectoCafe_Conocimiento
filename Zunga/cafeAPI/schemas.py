from pydantic import BaseModel
from typing import Optional, List
from datetime import date

#####Apache Jena --------------------
class fincaModel (BaseModel):
    id_finca: str          
    id_numeric: int        
    nombre: str            
    direccion: str         
    area: int              
    altitud: int
    FK_idPropietario: str
    lotes: List[str] = []         
    compras: List[str] = []

class loteModel (BaseModel):
    id_lote: str          
    id_numeric: int        
    nombre: str            
    area: int              
    cantidad: int          
    estado: bool          
    mantenimientos: List[str] = [] 
    suministros: List[str] = []    
    eventosRecoleccion: List[str] = []

class insumoModel (BaseModel):
    id_insumo: str
    id_numeric: int
    nombre: str
    precio: float
    tipo: str
    estado: bool
    unidadMedida: Optional[str] = None
    metodoAplicacion: Optional[str] = None
    compras: List[str] = []
    suministrosVinculados: List[str] = []

class compraModel (BaseModel):
    id_compra: str       
    id_numeric: int        
    fecha: str             
    cantidad: int          
    precio: float          
    estado: bool           
    id_insumo: str        
    id_finca: str

class recoleccionModel (BaseModel):
    id_recoleccion: str   
    id_numeric: int       
    fecha: str
    FK_idRecolector: str

class suministraInsumoModel(BaseModel):
    id_suministro: str   
    id_numeric: int  
    fecha: str             
    cantidad: int          
    estado: bool           
    id_insumo: str         
    id_lote: str

class mantenimientoModel (BaseModel):
    id_mantenimiento: str  
    id_numeric: int        
    fecha: str             
    tipo: str             
   

class eventoRecoleccionModel(BaseModel):
    id_evento: str      
    id_numeric: int       
    cantidad: int           
    id_lote: str            
    id_recoleccion: str

class inventarioModel(BaseModel):
    id_inventario: str     
    id_numeric: int         
    cantidad: int           
    fecha: str              
    unidadMedida: str  
    id_insumo: str    

### Postgres ----------------------

#Tipo doc
class tipoDocModel(BaseModel):
    id_doc: Optional[int] = None
    tipo: str
    class Config:
        from_attributes = True

#Persona
class personaModel(BaseModel):
    documento_persona: str
    nombre_persona: str
    edad_persona: Optional[int] = None
    telefono_persona: Optional[str] = None
    fk_tipo_documento: int

#Usuario
class usuarioModel(BaseModel):
    username: str
    password: str
    rol: str
    fk_persona: Optional[str] = None

class loginModel(BaseModel):
    username: str
    password: str
    class Config:
        from_attributes = True

#Propietario
class propietarioModel (BaseModel):
    id_propietario: str
    email_propietario: str
    estado_propietario: bool
    class Config:
        from_attributes = True

#Recolector
class recolectorModel (BaseModel):
    id_recolector: str
    fechainicio_recolector: date
    fechafin_recolector: Optional[date] = None
    estado_recolector: bool
    diastrabajados_recolector: int
    fk_id_propietario: Optional[str] = None
    fk_id_finca: Optional[str] = None
    class Config:
        from_attributes = True

#Reporte
class reporteModel(BaseModel):
    id_reporte: str
    fecha_reporte: date
    totaltecoleccion_reporte: float
    estado_reporte: bool
    fk_id_recolector: str
    class Config:
        from_attributes = True

#Pago
class pagoModel(BaseModel):
    id_pago: str
    fecha_pago: date
    preciokilo_pago: float
    estado_pago: bool
    monto_pago: float
    metodo_pago: str
    fk_id_reporte: str
    class Config:
        from_attributes = True


class catTipoInsumoModel(BaseModel):
    id_tipoinsumo: str
    nombre_tipo: str


class catUnidadMedidaCreateModel(BaseModel):
    nombre_unidadmedida: str


class catMetodoAplicacionCreateModel(BaseModel):
    nombre_metodoaplicacion: str