# proyectoCafe Conocimiento

Sistema de gestión de café: Django (web), FastAPI (API), PostgreSQL y ontología RDF en Apache Jena Fuseki.

## Estructura

- `cafeAPI/` — API FastAPI (puerto 8001), integración Fuseki y PostgreSQL
- `proyectoCafe/proyectoCafe/` — Aplicación Django (puerto 8000)
- `COMANDOS_INICIO.txt` — Pasos para levantar Fuseki, API y Django

## Requisitos

- Python 3.11+
- PostgreSQL (`bdcafe`)
- Apache Jena Fuseki (dataset `cafe`, puerto 3030)

## Inicio rápido

Ver `COMANDOS_INICIO.txt`.

## Utilidades

```powershell
cd cafeAPI
python limpiar_bd.py          # Limpia datos (conserva admin y catálogos)
python verify_consultas.py    # Verifica endpoints de consulta
```
