"""
Cliente SPARQL para Apache Jena Fuseki (dataset cafe, puerto 3030 por defecto).
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, List, Optional

import requests

CAFE_NS = "http://www.semanticweb.org/cafe/"
FUSEKI_QUERY_URL = os.getenv("FUSEKI_QUERY_URL", "http://localhost:3030/cafe/query")
FUSEKI_UPDATE_URL = os.getenv("FUSEKI_UPDATE_URL", "http://localhost:3030/cafe/update")
REQUEST_TIMEOUT = int(os.getenv("FUSEKI_TIMEOUT", "60"))

PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX cafe: <http://www.semanticweb.org/cafe/>
"""


class FusekiError(Exception):
    pass


def resource_uri(id_recurso: str) -> str:
    return f"<{CAFE_NS}{(id_recurso or '').strip()}>"


def _with_prefixes(query: str) -> str:
    q = (query or "").lstrip()
    if q.upper().startswith("PREFIX"):
        return query
    return PREFIXES + "\n" + query


def _escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def literal_term(val: Any, dtype: Optional[str] = None) -> str:
    if val is None:
        raise ValueError("valor literal no puede ser None")
    if isinstance(val, bool):
        return '"true"^^xsd:boolean' if val else '"false"^^xsd:boolean'
    if dtype == "int" or (dtype is None and isinstance(val, int) and not isinstance(val, bool)):
        return f'"{int(val)}"^^xsd:int'
    if dtype == "double" or (dtype is None and isinstance(val, float)):
        return f'"{float(val)}"^^xsd:double'
    if dtype == "boolean":
        return '"true"^^xsd:boolean' if val else '"false"^^xsd:boolean'
    return f'"{_escape_literal(str(val))}"^^xsd:string'


def _dtype_for_value(val: Any) -> str:
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "double"
    return "string"


def binding_to_python(cell: Optional[dict]) -> Any:
    if not cell:
        return None
    value = cell.get("value")
    if value is None:
        return None
    dt = cell.get("datatype") or ""
    if "int" in dt:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if "double" in dt or "decimal" in dt or "float" in dt:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if "boolean" in dt:
        return str(value).lower() in ("true", "1")
    return value


def sparql_query(query: str) -> dict:
    try:
        r = requests.post(
            FUSEKI_QUERY_URL,
            data=_with_prefixes(query).encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        raise FusekiError(f"Error consultando Fuseki ({FUSEKI_QUERY_URL}): {exc}") from exc


def sparql_update(update: str) -> None:
    try:
        r = requests.post(
            FUSEKI_UPDATE_URL,
            data=_with_prefixes(update).encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        raise FusekiError(f"Error actualizando Fuseki ({FUSEKI_UPDATE_URL}): {exc}") from exc


def sparql_ask(query: str) -> bool:
    data = sparql_query(query)
    return bool(data.get("boolean", False))


def sparql_select(query: str) -> List[SimpleNamespace]:
    data = sparql_query(query)
    vars_ = data.get("head", {}).get("vars", [])
    rows: List[SimpleNamespace] = []
    for binding in data.get("results", {}).get("bindings", []):
        row_dict = {v: binding_to_python(binding.get(v)) for v in vars_}
        rows.append(SimpleNamespace(**row_dict))
    return rows


def count_triples() -> int:
    rows = sparql_select("SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
    if not rows:
        return 0
    return int(rows[0].c or 0)


def resource_exists(id_recurso: str) -> bool:
    uri = resource_uri(id_recurso)
    return sparql_ask(
        f"""
        ASK {{
          {{ {uri} ?p ?o }}
          UNION
          {{ ?s ?p {uri} }}
        }}
        """
    )


def resource_has_subject(id_recurso: str) -> bool:
    uri = resource_uri(id_recurso)
    return sparql_ask(f"ASK {{ {uri} ?p ?o }}")


def delete_resource(id_recurso: str) -> None:
    uri = resource_uri(id_recurso)
    sparql_update(
        f"""
        DELETE WHERE {{
          {{ {uri} ?p ?o }}
          UNION
          {{ ?s ?p {uri} }}
        }}
        """
    )


def insert_data(turtle_body: str) -> None:
    body = (turtle_body or "").strip()
    if not body:
        return
    sparql_update(f"INSERT DATA {{ {body} }}")


def add_object_triple(subject_id: str, prop: str, object_id: str) -> None:
    insert_data(f"{resource_uri(subject_id)} cafe:{prop} {resource_uri(object_id)} .")


def build_individual_triples(
    id_uri: str,
    tipo_clase: str,
    id_numero: int,
    datos: Optional[dict] = None,
    relaciones: Optional[dict] = None,
) -> str:
    datos = datos or {}
    relaciones = relaciones or {}
    subj = resource_uri(id_uri)
    parts = [f"{subj} a cafe:{tipo_clase} ;", f"  cafe:id {literal_term(id_numero, 'int')} ;"]
    for prop, valor in datos.items():
        if valor is not None:
            parts.append(f"  cafe:{prop} {literal_term(valor, _dtype_for_value(valor))} ;")
    for prop, id_destino in relaciones.items():
        if id_destino:
            parts.append(f"  cafe:{prop} {resource_uri(str(id_destino))} ;")
    parts[-1] = parts[-1].rstrip(" ;") + " ."
    return "\n".join(parts)


def guardar_individuo(
    id_uri: str,
    tipo_clase: str,
    id_numero: int,
    datos: Optional[dict] = None,
    relaciones: Optional[dict] = None,
) -> None:
    if resource_has_subject(id_uri):
        raise ValueError(f"El individuo '{id_uri}' ya existe.")
    insert_data(build_individual_triples(id_uri, tipo_clase, id_numero, datos, relaciones))


def get_resource_properties(id_recurso: str) -> tuple[dict, dict]:
    uri = resource_uri(id_recurso)
    rows = sparql_select(f"SELECT ?p ?o WHERE {{ {uri} ?p ?o . }}")
    detalles: dict = {}
    relaciones: dict = {}
    for row in rows:
        p = str(row.p or "")
        nombre_prop = p.rsplit("/", 1)[-1]
        if nombre_prop == "type":
            continue
        o_val = row.o
        if o_val is None:
            continue
        if isinstance(o_val, str) and (o_val.startswith("http://") or o_val.startswith("https://")):
            relaciones[nombre_prop] = o_val.rsplit("/", 1)[-1]
        else:
            detalles[nombre_prop] = o_val
    return detalles, relaciones


def delete_literal_properties(id_recurso: str) -> None:
    uri = resource_uri(id_recurso)
    sparql_update(
        f"""
        DELETE WHERE {{
          {uri} ?p ?o .
          FILTER(isLiteral(?o))
        }}
        """
    )


def set_literal_properties(id_recurso: str, nuevos_datos: dict) -> None:
    if not nuevos_datos:
        return
    lines = []
    subj = resource_uri(id_recurso)
    for propiedad, valor in nuevos_datos.items():
        lines.append(f"{subj} cafe:{propiedad} {literal_term(valor, _dtype_for_value(valor))} .")
    insert_data("\n".join(lines))


def set_predicate_literal(id_recurso: str, propiedad: str, valor: Any) -> None:
    uri = resource_uri(id_recurso)
    sparql_update(f"DELETE WHERE {{ {uri} cafe:{propiedad} ?o . }}")
    insert_data(f"{uri} cafe:{propiedad} {literal_term(valor, _dtype_for_value(valor))} .")


def get_rdf_type(id_recurso: str) -> Optional[str]:
    uri = resource_uri(id_recurso)
    rows = sparql_select(f"SELECT ?t WHERE {{ {uri} rdf:type ?t . }} LIMIT 1")
    if not rows:
        return None
    return str(rows[0].t or "")


def restore_rdf_type(id_recurso: str, tipo_uri: str) -> None:
    if not tipo_uri:
        return
    uri = resource_uri(id_recurso)
    insert_data(f"{uri} rdf:type <{tipo_uri}> .")


def propietario_de_finca(finca_id: str) -> Optional[str]:
    fid = (finca_id or "").strip()
    if not fid:
        return None
    if not resource_has_subject(fid):
        return None
    uri = resource_uri(fid)
    rows = sparql_select(f"SELECT ?o WHERE {{ {uri} cafe:fk_idPropietario ?o . }} LIMIT 1")
    if not rows:
        return None
    o = rows[0].o
    if o is None:
        return None
    return str(o).split("/")[-1]


_CAFE_ID = "<http://www.semanticweb.org/cafe/id>"


def clear_all_individuals() -> None:
    """Elimina individuos (tienen cafe:id); conserva TBox de la ontología."""
    sparql_update(
        f"""
        DELETE WHERE {{
          ?s ?p ?o .
          ?s {_CAFE_ID} ?n .
        }}
        """
    )
    sparql_update(
        f"""
        DELETE WHERE {{
          ?s ?p ?o .
          ?o {_CAFE_ID} ?n .
        }}
        """
    )


def kg_recolector_en_fecha(recolector_id: str, fecha_str: str) -> float:
    rid = (recolector_id or "").strip()
    fs = (fecha_str or "").strip()[:10]
    if not rid or not fs:
        return 0.0
    rows = sparql_select(
        f"""
        SELECT (SUM(xsd:decimal(?q)) AS ?total) WHERE {{
          ?rec a cafe:recoleccion .
          ?rec cafe:fk_idRecolector ?rid .
          ?rec cafe:fecha ?f .
          FILTER(
            (?rid = "{_escape_literal(rid)}") ||
            (isIRI(?rid) && STRENDS(STR(?rid), "/{_escape_literal(rid)}"))
          )
          FILTER(STRSTARTS(STR(?f), "{_escape_literal(fs)}"))
          ?ev cafe:generaRecoleccion ?rec .
          ?ev cafe:cantidad ?q .
        }}
        """
    )
    if not rows or rows[0].total is None:
        return 0.0
    try:
        return float(rows[0].total)
    except (TypeError, ValueError):
        return 0.0
