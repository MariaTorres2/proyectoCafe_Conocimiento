"""
Validación de entrada — módulo Finanzas (propietario / admin vía node_compat).

Alineado con el JSON que envía `vista_propietario.html` (liquidación, reporte diario, etc.).
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class FinanzasKgSugeridoQuery(BaseModel):

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id_recolector: str = Field(min_length=1, max_length=64)
    fecha: str = Field(
        min_length=8,
        max_length=32,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Fecha ISO (input type=date)",
    )


class FinanzasDiaLiquidacion(BaseModel):

    model_config = ConfigDict(extra="ignore")

    fecha: str = Field(
        min_length=8,
        max_length=32,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    ausente: bool = False
    kg_dia: float = Field(ge=0, default=0)
    precio_kilo: float = Field(ge=0, default=0)
    metodo_pago: str = Field(default="Efectivo", max_length=50)


class FinanzasGenerarPagoBody(BaseModel):

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id_recolector: str = Field(min_length=1, max_length=64)
    dias: list[FinanzasDiaLiquidacion] = Field(default_factory=list)


class ReporteDiarioBody(BaseModel):

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id_recolector: str = Field(
        validation_alias=AliasChoices("id_recolector", "fk_id_recolector"),
        min_length=1,
        max_length=64,
    )
    fecha: str = Field(
        validation_alias=AliasChoices("fecha", "fecha_reporte"),
        min_length=8,
        max_length=32,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


class LiquidacionRecolectorBody(BaseModel):

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id_recolector: str = Field(
        validation_alias=AliasChoices("id_recolector", "documento"),
        min_length=1,
        max_length=64,
    )
    precio_kilo: float = Field(ge=0, default=0)
