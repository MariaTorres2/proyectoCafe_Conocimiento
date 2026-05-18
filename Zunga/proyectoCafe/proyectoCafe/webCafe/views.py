import requests, json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from functools import wraps

def _volver_url(request):
    rol = (request.session.get("rol") or "").strip().lower()
    if rol == "admin":
        return "/vista_admin/"
    if rol == "recolector":
        return "/vista_recolector/"
    return "/vista_propietario/"


def _session_rol(request):
    return (request.session.get("rol") or "").strip().lower()


def _require_authenticated(request):
    if not request.session.get("usuario"):
        return JsonResponse({"error": "No autenticado", "message": "Inicie sesión."}, status=401)
    return None


def _crud_propietario_entidad_solo_admin(request, nombre_tabla):
    if (nombre_tabla or "").strip().lower() == "propietario" and _session_rol(request) != "admin":
        return JsonResponse({"error": "Acceso denegado"}, status=403)
    return None


def _propietario_posee_recolector(request, id_recolector):
    """True si el propietario logueado es dueño del contrato (fk_id_propietario)."""
    fk = (request.session.get("fk_persona") or "").strip()
    try:
        r = requests.get(f"http://127.0.0.1:8001/consultarRegistro/recolector/{id_recolector}")
        if r.status_code != 200:
            return False
        row = r.json()
        return str(row.get("fk_id_propietario") or "") == fk
    except Exception:
        return False


def _puede_corregir_recolector(request, id_recolector):
    rol = _session_rol(request)
    if rol == "admin":
        return True
    if rol == "propietario":
        return _propietario_posee_recolector(request, id_recolector)
    if rol == "recolector":
        return str(id_recolector).strip() == str(request.session.get("fk_persona") or "").strip()
    return False


def _puede_eliminar_recolector(request, id_recolector):
    rol = _session_rol(request)
    if rol == "admin":
        return True
    if rol == "propietario":
        return _propietario_posee_recolector(request, id_recolector)
    return False


def reporte_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = (request.session.get("rol") or "").strip().lower()
        if rol not in ["admin", "propietario", "recolector"]:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view



def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get('rol') != 'admin':
            messages.error(request, "Acceso denegado. Se requieren permisos de administrador.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def propietario_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'propietario']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_or_propietario_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'propietario']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def recolector_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'recolector']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

_TABLA_REDIRECT = {
    "propietario": "/propietario/",
    "persona": "/persona/",
    "finca": "/finca/",
    "recolector": "/recolector/",
    "lote": "/lote/",
    "insumo": "/insumo/",
    "recoleccion": "/recoleccion/",
}


def _redirect_por_tabla(nombre_tabla: str):
    return redirect(_TABLA_REDIRECT.get((nombre_tabla or "").lower(), "/"))

def inicio(request):
    if request.method == "POST":
        user = (request.POST.get("username") or "").strip()
        pasw = (request.POST.get("password") or "").strip()
        
        try:
            url_api = "http://127.0.0.1:8001/login"
            response = requests.post(url_api, json={"username": user, "password": pasw})
            
            if response.status_code == 200:
                data = response.json()
                request.session['usuario'] = data['username']
                rol = (data.get('rol') or '').strip().lower()
                request.session['fk_persona'] = data.get('fk_persona')
                request.session['rol'] = rol
                
                if rol == 'admin':
                    return redirect("/vista_admin/")
                elif rol == 'propietario':
                    return redirect("/vista_propietario/")
                elif rol == 'recolector':
                    return redirect("/vista_recolector/")
            else:
                messages.error(request, "Usuario o contraseña incorrectos")
        except Exception as e:
            messages.error(request, "Error de conexión con el servidor de autenticación")
            
    return render(request, "inicio.html")


############## Get 

 ## ---postgres ----------------

# Get un registro
def consultar_registro(request, nombre_tabla, id_registro):
    deny = _require_authenticated(request)
    if deny:
        return deny
    deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
    if deny:
        return deny
    # En FastAPI: GET es /consultarRegistro/... ( /registros/... es DELETE )
    url_api = f"http://127.0.0.1:8001/consultarRegistro/{nombre_tabla}/{id_registro}"
    try:
        response = requests.get(url_api)
        if response.status_code == 200:
            data = response.json()
            if nombre_tabla.lower() == "persona" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({"error": "Acceso denegado"}, status=403)
            # Si estamos buscando una persona, vamos a ver qué roles tiene
            if nombre_tabla.lower() == "persona":
                roles = []
                # Check Propietario
                if requests.get(f"http://127.0.0.1:8001/consultarRegistro/propietario/{id_registro}").status_code == 200:
                    roles.append("Propietario")
                # Check Recolector
                if requests.get(f"http://127.0.0.1:8001/consultarRegistro/recolector/{id_registro}").status_code == 200:
                    roles.append("Recolector")
                
                if isinstance(data, dict):
                    data['rol'] = ", ".join(roles) if roles else "Sin Rol"
                elif hasattr(data, 'data') and isinstance(data.data, dict):
                    data.data['rol'] = ", ".join(roles) if roles else "Sin Rol"

            if nombre_tabla.lower() == "recolector" and _session_rol(request) == "propietario":
                fk_sess = (request.session.get("fk_persona") or "").strip()
                fk_row = data.get("fk_id_propietario") if isinstance(data, dict) else None
                if str(fk_row or "") != fk_sess:
                    return JsonResponse({'error': 'Acceso denegado'}, status=403)

            if nombre_tabla.lower() == "recolector" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({'error': 'Acceso denegado'}, status=403)

            return JsonResponse(data)
        else:
            return JsonResponse({'error': 'Registro no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'La API no responde'}, status=500)

# Get todos los registros
def get_todos(request, nombre_tabla):
    deny = _require_authenticated(request)
    if deny:
        return deny
    deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
    if deny:
        return deny
    t = (nombre_tabla or "").strip().lower()
    if t == "persona" and _session_rol(request) == "recolector":
        return JsonResponse({"error": "Acceso denegado"}, status=403)
    url_api = f"http://127.0.0.1:8001/detallesT/{nombre_tabla}"
    try:
        response = requests.get(url_api)
        if response.status_code == 200:
            rows = response.json()
            rol = _session_rol(request)
            if t == "recolector" and rol == "propietario":
                fk_sess = (request.session.get("fk_persona") or "").strip()
                if isinstance(rows, list):
                    rows = [r for r in rows if str(r.get("fk_id_propietario") or "") == fk_sess]
            if t == "recolector" and rol == "recolector":
                fk_sess = str(request.session.get("fk_persona") or "").strip()
                if isinstance(rows, list):
                    rows = [r for r in rows if str(r.get("id_recolector") or "") == fk_sess]
            return JsonResponse(rows, safe=False)
        return JsonResponse({"error": response.text or "Error API"}, status=response.status_code)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500) 

##Get temporal
def obtener_persona_temporal(request):
    datos = request.session.get('datos_persona_temp')
    if datos:
        return JsonResponse({"success": True, "data": datos})
    return JsonResponse({"success": False, "message": "No hay datos temporales"})

### ------apache jena-----------------------

def consulta_rdf(request, tipo_consulta, nombre_tabla, id):
    template = f"{nombre_tabla.lower()}.html"
    if tipo_consulta == 'detalle':
        url_api = f"http://127.0.0.1:8001/detalle/{id}"
    else:
        url_api = f"http://127.0.0.1:8001/detallesClase/{id}"

    try:
        response = requests.get(url_api)
        if response.status_code == 200:
            datos = response.json()
            return render(request, template, {
                'resultado': datos,
                'tipo': tipo_consulta,
                'nombre': id,
                'nombre_tabla': nombre_tabla 
            })
        else:
            messages.error(request, "El recurso no existe")
    except Exception as e:
        messages.error(request, f"Error de conexión")
    return render(request, template)

############ Editar -----------------------------------

# Postgres
def corregir_registro(request, nombre_tabla, id_registro):
    if request.method == 'POST':
        try:
            deny = _require_authenticated(request)
            if deny:
                return deny
            deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
            if deny:
                return deny
            tabla = (nombre_tabla or "").strip().lower()
            if tabla == "recolector" and not _puede_corregir_recolector(request, id_registro):
                return JsonResponse({"status": "error", "message": "Acceso denegado"}, status=403)
            if tabla == "persona" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({"status": "error", "message": "Acceso denegado"}, status=403)
            actualiza= json.loads(request.body)         
            url_api = f"http://127.0.0.1:8001/corregirRegistro/{nombre_tabla}/{id_registro}"
            response = requests.patch(url_api, json=actualiza)      
            if response.status_code == 200:
                return JsonResponse({"status": "success", "message": "Registro actualizado correctamente"})
            else:
                try:
                    msg = response.json().get("detail", "Error en la API")
                except Exception:
                    msg = response.text or "Error en la API"
                return JsonResponse({"status": "error", "message": msg}, status=response.status_code or 400)
                
        except Exception as e:
            return JsonResponse({"status": "error", "message": "Error en la API"})
            
    return JsonResponse({"status": "error", "message": "Error en la API"})

# Apache jena
def editar_individuo(request, id_recurso, nombre_tabla):
    if request.method == 'POST':  
        nuevos_datos = {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'}    
        url_api = f"http://127.0.0.1:8001/corregirIndividuo/{id_recurso}"
        template = f"webCafe/{nombre_tabla.lower()}.html"
        try:
            response = requests.put(url_api, json=nuevos_datos)
            if response.status_code == 200:
                messages.success(request, "Información actualizada")
                return _redirect_por_tabla(nombre_tabla)
            else:
                messages.error(request, "Error al actualizar")
        except Exception as e:
            messages.error(request, "Error de conexión")
    return _redirect_por_tabla(nombre_tabla)

########### Eliminar ----------------------------------

# Postgres
def eliminar_registro(request, nombre_tabla, id_registro):
    try:
        deny = _require_authenticated(request)
        if deny:
            return deny
        deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
        if deny:
            return deny
        tabla = (nombre_tabla or "").lower()
        doc = str(id_registro)

        if tabla == "recolector":
            if not _puede_eliminar_recolector(request, doc):
                return JsonResponse({
                    "status": "error",
                    "message": "Acceso denegado.",
                }, status=403)

        if tabla == "persona" and _session_rol(request) == "recolector":
            return JsonResponse({"status": "error", "message": "Acceso denegado."}, status=403)
        if tabla in ["propietario", "recolector"]:
            # SI ES PROPIETARIO, también eliminar sus fincas (Cascada)
            if tabla == "propietario":
                try:
                    from .node_compat import _rdf_list
                    fincas = _rdf_list("finca")
                    for fid, props in fincas.items():
                        if str(props.get("fk_idPropietario")) == str(id_registro):
                            requests.delete(f"http://127.0.0.1:8001/individuos/{fid}")
                except Exception as e_finca:
                    print(f"Error eliminando fincas en cascada: {e_finca}")

            # 1. Eliminar el rol (Propietario/Recolector); la API aplica cascada SQL (FK recolector/reporte/pago)
            url_rol = f"http://127.0.0.1:8001/registros/{nombre_tabla}/{id_registro}"
            r_rol = requests.delete(url_rol)
            if r_rol.status_code != 200:
                try:
                    msg = r_rol.json().get("detail", r_rol.text)
                except Exception:
                    msg = r_rol.text or "Error al eliminar el rol"
                return JsonResponse({"status": "error", "message": str(msg)}, status=400)

            # 2. Eliminar la Persona asociada (usuario ya eliminado en cascada al borrar Persona vía API)
            url_persona = f"http://127.0.0.1:8001/registros/Persona/{id_registro}"
            response = requests.delete(url_persona)
        else:
            # Persona: un solo DELETE; FastAPI elimina usuario por fk_persona, libera recolectores del propietario y cascada recolector
            url_api = f"http://127.0.0.1:8001/registros/{nombre_tabla}/{id_registro}"
            response = requests.delete(url_api)

        if response.status_code == 200:
            return JsonResponse({
                "status": "success", 
                "message": f"Registro {id_registro} eliminado correctamente (Cascada aplicada)."
            })
        else:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text or "La API falló al eliminar el registro principal."
            return JsonResponse({
                "status": "error",
                "message": str(detail),
            }, status=400 if response.status_code < 500 else 502)
            
    except Exception as e:
        return JsonResponse({
            "status": "error", 
            "message": f"Error de conexión: {str(e)}"
        }, status=500)

# Apache jena
def eliminar_individuo(request, id_recurso, nombre_tabla):
    url_api = f"http://127.0.0.1:8001/individuos/{id_recurso}"
    template = f"webCafe/{nombre_tabla.lower()}.html"
    try:
        response = requests.delete(url_api)
        if response.status_code == 200:
            messages.success(request, "El recurso se ha eliminado")
        else:
            messages.error(request, "No es posible eliminarlo.")
            
    except Exception as e:
        messages.error(request, "Error de conexión")

    return _redirect_por_tabla(nombre_tabla)

############ Post ---------------------------------------
# Persona
@admin_or_propietario_required
@ensure_csrf_cookie
def persona_page(request):
    return render(request, 'persona.html', {"volver_url": _volver_url(request), "is_admin": request.session.get("rol") == "admin"})

@admin_or_propietario_required
def insert_persona(request):
    if request.method == 'POST':
        try:
            # Esta ruta se usa como parte del flujo Persona -> Rol (propietario/recolector)
            # Evitamos crear Personas “sueltas” sin pasar por ese flujo.
            if 'datos_persona_temp' not in request.session:
                return JsonResponse({
                    "success": False,
                    "message": "Primero registra la persona como temporal y crea el rol (Propietario o Recolector)."
                }, status=400)
            datos= {
            "documento_persona": request.POST.get('documento_persona'),
            "nombre_persona": request.POST.get('nombre_persona'),
            "edad_persona": int(request.POST.get('edad_persona')),
            "telefono_persona": request.POST.get('telefono_persona'),
            "fk_tipo_documento": int(request.POST.get('id_tipodoc'))
              }
            url_api = "http://127.0.0.1:8001/personas"
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                return JsonResponse({
                    "success": True,
                    "data": datos
                })
            else:
                return JsonResponse({
                    "success": False,
                    "message": "Error en la API"
                })
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": str(e)
            })
        
## Perosna temporal
@admin_or_propietario_required
def insert_persona_temporal(request):
    if request.method == 'POST':
        datos = {
            "documento_persona": request.POST.get('documento_persona'),
            "fk_tipo_documento": int(request.POST.get('id_tipodoc')),
            "nombre_persona": request.POST.get('nombre_persona'),
            "edad_persona": int(request.POST.get('edad_persona')),
            "telefono_persona": request.POST.get('telefono_persona')
        }
        request.session['datos_persona_temp'] = datos
        return JsonResponse({
            "success": True, 
            "data": datos
        })
    
    return JsonResponse({"success": False})


# Propietario
@admin_required
def propietario_page(request):
    return render(request, 'propietario.html', {"volver_url": _volver_url(request)})


@admin_required
def insert_propietario(request):
    if request.method == 'POST':
        try:
            id_propietario = request.POST.get('id_propietario')
            email = request.POST.get('email_propietario')
            estado = request.POST.get('estado_propietario')
            username = (request.POST.get("username_propietario") or "").strip()
            password = (request.POST.get("password_propietario") or "").strip()
            # Alta: activo por defecto si no viene estado (formulario sin selector)
            if estado == "0":
                estado_bool = False
            elif estado == "1":
                estado_bool = True
            else:
                estado_bool = True
            if not id_propietario or not email or not username or not password:
                return JsonResponse({
                    "success": False,
                    "message": "Campos incompletos"
                }, status=400)
            datos = {
                "id_propietario": id_propietario,
                "email_propietario": email,
                "estado_propietario": estado_bool
            }

            url_api = "http://127.0.0.1:8001/propietarios"
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                # Crear usuario de login asociado al propietario
                r_user = requests.post("http://127.0.0.1:8001/usuarios", json={
                    "username": username,
                    "password": password,
                    "rol": "propietario",
                    "fk_persona": str(id_propietario),
                })
                if r_user.status_code != 200:
                    # Rollback: eliminar propietario + persona + usuario (si alcanzó a crearse)
                    try:
                        requests.delete(f"http://127.0.0.1:8001/registros/propietario/{id_propietario}")
                        requests.delete(f"http://127.0.0.1:8001/registros/persona/{id_propietario}")
                        requests.delete(f"http://127.0.0.1:8001/registros/usuario/{id_propietario}")
                    except Exception:
                        pass
                    try:
                        detail = r_user.json().get("detail")
                    except Exception:
                        detail = None
                    return JsonResponse({
                        "success": False,
                        "message": detail or "No se pudo crear el usuario del propietario"
                    }, status=400)
                if 'datos_persona_temp' in request.session:
                    del request.session['datos_persona_temp']
                return JsonResponse({
                    "success": True,
                    "data": {**datos, "username": username}
                })
            else:
                return JsonResponse({
                    "success": False,
                    "message": "Error en API Propietarios",
                })

        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": str(e),
            })

    return JsonResponse({
        "success": False,
    })



# Recoleccion
@admin_or_propietario_required
def recoleccion_page(request):
    return render(request, 'recoleccion.html', {"volver_url": _volver_url(request)})

@admin_or_propietario_required
def insert_recoleccion(request):
    if request.method == 'POST':
        datos = {
            "id_recoleccion": request.POST.get('id_recoleccion'),
            "id_numeric": int(request.POST.get('id_numeric') or 0),
            "fecha": request.POST.get('fecha'),
            "FK_idRecolector": str(request.POST.get('fk_idRecolector') or ''),
        }
        url_api = "http://127.0.0.1:8001/recolecciones"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                return render(request, 'recoleccion.html', {'recoleccion': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'recoleccion.html')

# Recolector
@admin_or_propietario_required
@ensure_csrf_cookie
def recolector_page(request):
    rol = (request.session.get("rol") or "").strip().lower()
    return render(request, 'recolector.html', {
        "volver_url": _volver_url(request),
        "is_propietario": rol == "propietario",
        "is_admin": rol == "admin",
        "propietario_doc": (request.session.get("fk_persona") or ""),
    })

@admin_or_propietario_required
def insert_recolector(request):
    if request.method == 'POST':
        try:
            datos = {
                "id_recolector": request.POST.get('id_recolector'),
                "fechainicio_recolector": request.POST.get('fechainicio_recolector'),
                "fechafin_recolector": request.POST.get('fechafin_recolector') or None,
                "estado_recolector": request.POST.get('estado_recolector') == "1",
                "diastrabajados_recolector": int(request.POST.get('diastrabajados_recolector') or 0)
            }
            rol = (request.session.get("rol") or "").strip().lower()
            fk_fin = (request.POST.get("fk_id_finca") or "").strip()
            if rol == "propietario":
                datos["fk_id_propietario"] = request.session.get("fk_persona")
                if not fk_fin:
                    return JsonResponse({
                        "success": False,
                        "message": "Debe seleccionar una finca",
                    }, status=400)
                datos["fk_id_finca"] = fk_fin
            elif rol == "admin":
                fp = (request.POST.get("fk_id_propietario") or "").strip()
                if fp:
                    datos["fk_id_propietario"] = fp
                if fk_fin:
                    datos["fk_id_finca"] = fk_fin

            url_api = "http://127.0.0.1:8001/recolectores"
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                if 'datos_persona_temp' in request.session:
                    del request.session['datos_persona_temp']
                try:
                    body_api = response.json()
                except Exception:
                    body_api = {}
                out = {
                    "success": True,
                    "data": datos,
                }
                av = body_api.get("aviso")
                if av:
                    out["aviso"] = av
                return JsonResponse(out)
            else:
                try:
                    msg = response.json().get("detail", response.text)
                except Exception:
                    msg = response.text or "Error en la API de Recolectores"
                return JsonResponse({
                    "success": False,
                    "message": str(msg),
                }, status=response.status_code if response.status_code < 500 else 400)

        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": str(e)
            })
    return render(request, 'recolector.html')

# Reporte
@reporte_access_required
def reporte_page(request):
    rol = (request.session.get("rol") or "").strip().lower()
    return render(request, 'reporte.html', {
        "volver_url": _volver_url(request),
        "is_recolector": rol == "recolector",
    })

@reporte_access_required
def insert_reporte(request):
    if request.method == 'POST':
        est = request.POST.get('estado_reporte')
        datos = {
            "id_reporte": str(request.POST.get('id_reporte') or ''),
            "fecha_reporte": request.POST.get('fecha_reporte'),
            "totaltecoleccion_reporte": float(request.POST.get('totalrecoleccion_reporte') or 0),
            "estado_reporte": est in ('1', 'true', 'True', 'on', 'si'),
            "fk_id_recolector": str(request.POST.get('fk_id_recolector') or ''),
        }
        if _session_rol(request) == "recolector":
            doc = str(request.session.get("fk_persona") or "").strip()
            if str(datos["fk_id_recolector"]).strip() != doc:
                messages.error(request, "Solo puede registrar reportes asociados a su documento.")
                return render(request, 'reporte.html')
        url_api = "http://127.0.0.1:8001/reportes"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Reporte registrado")
                return render(request, 'reporte.html', {
                    'reporte': datos,
                    'respuesta_api': response.json()
                })
            else:
                messages.error(request, "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'reporte.html')

# Finca
@admin_or_propietario_required
def finca_page(request):
    return render(request, 'finca.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_finca(request):
    if request.method == 'POST':
        datos = {
            "id_finca": request.POST.get('id_finca'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "direccion": request.POST.get('direccion'),
            "area": float(request.POST.get('area')),
            "altitud": float(request.POST.get('altitud')),
            "FK_idPropietario": str(request.POST.get('FK_idpropietario') or ''),
            "lotes": request.POST.getlist('lotes'),
            "compras": request.POST.getlist('compras')
        }
        if _session_rol(request) == "propietario":
            datos["FK_idPropietario"] = str(request.session.get("fk_persona") or "")
        url_api = "http://127.0.0.1:8001/fincas"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Finca registrada")
                return render(request, 'finca.html', {
                    'finca': datos,
                    'respuesta_api': response.json()
                })
            else:
                messages.error(request, "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'finca.html')

# Insumo
@admin_or_propietario_required
def insumo_page(request):
    return render(request, 'insumo.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_insumo(request):
    if request.method == 'POST':
        datos = {
            "id_insumo": request.POST.get('id_insumo'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "precio": float(request.POST.get('precio')),
            "tipo": request.POST.get('tipo'),
            "estado": request.POST.get('estado'),
            "compras": request.POST.getlist('compras'),
            "suministrosVinculados": request.POST.getlist('suministrosVinculados')
        }
        url_api = "http://127.0.0.1:8001/insumos"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                return render(request, 'insumo.html', {'insumo': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'insumo.html')


# Pago
@admin_or_propietario_required
def pago_page(request):
    return render(request, 'pago.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_pago(request):
    if request.method == 'POST':
        est = request.POST.get('estado_pago')
        datos = {
            "id_pago": str(request.POST.get('id_pago') or ''),
            "fecha_pago": request.POST.get('fecha_pago'),
            "preciokilo_pago": float(request.POST.get('preciokilo_pago') or 0),
            "estado_pago": est in ('1', 'true', 'True', 'on', 'si'),
            "monto_pago": float(request.POST.get('monto_pago') or 0),
            "metodo_pago": str(request.POST.get('metodo_pago') or 'Efectivo'),
            "fk_id_reporte": str(request.POST.get('fk_id_reporte') or ''),
        }
        url_api = "http://127.0.0.1:8001/pagos"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Pago registrado")
                return render(request, 'pago.html', {
                    'pago': datos,
                    'respuesta_api': response.json()
                })
            else:
                messages.error(request, "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'pago.html')

# Matenimiento
@admin_or_propietario_required
def mantenimiento_page(request):
    return render(request, 'mantenimiento.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_mantenimiento(request):
    if request.method == 'POST':
        datos = {
            "id_mantenimiento": request.POST.get('id_mantenimiento'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "fecha": request.POST.get('fecha'),
            "tipo": request.POST.get('tipo')
        }
        url_api = "http://127.0.0.1:8001/mantenimientos"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Mantenimiento registrado")
                return render(request, 'mantenimiento.html', {
                    'mantenimiento': datos,
                    'respuesta_api': response.json()
                })
            else:
                messages.error(request, "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'mantenimiento.html')

# Evento recoleccion
@propietario_required
def insert_evento_recoleccion(request):
    if request.method == 'POST':
        datos = {
            "id_evento": request.POST.get('id_evento'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "cantidad": int(request.POST.get('cantidad')),
            "id_lote": request.POST.get('id_lote'),
            "id_recoleccion": request.POST.get('id_recoleccion')
        }
        url_api = "http://127.0.0.1:8001/eventosRecoleccion"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Evento registrado")
                return render(request, 'recoleccion.html', {
                    'evento': datos,
                    'respuesta_api': response.json()
                })
            else:
                messages.error(request, "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'recoleccion.html')

# Inventario
@propietario_required
def insert_inventario(request):
    if request.method == 'POST':
        datos = {
            "id_inventario": request.POST.get('id_inventario'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "cantidad": int(request.POST.get('cantidad')),
            "fecha": request.POST.get('fecha'),
            "unidadMedida": request.POST.get('unidadMedida'),
            "id_insumo": request.POST.get('id_insumo')
        }
        url_api = "http://127.0.0.1:8001/inventarios"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Inventario registrado")
                return render(request, 'inventario.html', {
                    'inventario': datos,
                    'respuesta_api': response.json()
                })
            messages.error(request, response.text or "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
        except Exception as ex:
            messages.error(request, str(ex))
    return render(request, 'inventario.html')

#SuministraInsumo
@propietario_required
def insert_suministro(request):
    if request.method == 'POST':
        datos = {
            "id_suministro": request.POST.get('id_suministro'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "fecha": request.POST.get('fecha'),
            "cantidad": int(request.POST.get('cantidad')),
            "estado": request.POST.get('estado') == 'true', # Convierte a booleano
            "id_insumo": request.POST.get('id_insumo'),
            "id_lote": request.POST.get('id_lote')
        }
        url_api = "http://127.0.0.1:8001/suministros"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Suministro registrado")
                return render(request, 'suministros.html', {
                    'suministro': datos,
                    'respuesta_api': response.json()
                })
            messages.error(request, response.text or "Error en la API")
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
        except Exception as ex:
            messages.error(request, str(ex))
    return render(request, 'suministros.html')

# Tipo doc
@admin_or_propietario_required
def tipo_doc_page(request):
    return render(request, 'tipo_doc.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_tipodocumento(request):
    if request.method == 'POST':
        datos = {
            "id_doc": int(request.POST.get('id_doc')),
            "tipo": request.POST.get('tipo')
        }
        url_api = "http://127.0.0.1:8001/tipoDocumento"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Tipo de documento registrado")
                return render(request, 'tipo_doc.html', {'tipo_doc': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'tipo_doc.html')

# Compra
@admin_or_propietario_required
def compra_page(request):
    return render(request, 'compra.html', {"volver_url": _volver_url(request)})


@propietario_required
def inventario_page(request):
    return render(request, 'inventario.html', {"volver_url": _volver_url(request)})


@propietario_required
def suministro_page(request):
    return render(request, 'suministros.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_compra(request):
    if request.method == 'POST':
        est = request.POST.get('estado')
        datos = {
            "id_compra": request.POST.get('id_compra'),
            "id_numeric": int(request.POST.get('id_numeric') or 0),
            "fecha": request.POST.get('fecha'),
            "cantidad": int(float(request.POST.get('cantidad') or 0)),
            "precio": float(request.POST.get('precio') or 0),
            "estado": est in ('1', 'true', 'True', 'on', 'si'),
            "id_insumo": request.POST.get('id_insumo'),
            "id_finca": request.POST.get('id_finca')
        }
        url_api = "http://127.0.0.1:8001/compras"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Compra registrada")
                return render(request, 'compra.html', {'compra': datos, 'respuesta_api': response.json()})
            messages.error(request, response.text or "Error al registrar compra en la API")
        except Exception as ex:
            messages.error(request, f"Error de conexión: {ex}")
    return render(request, 'compra.html')


# Lote
@admin_or_propietario_required
def lote_page(request):
    return render(request, 'lote.html', {"volver_url": _volver_url(request)})

@propietario_required
def insert_lote(request):
    if request.method == 'POST':
        datos = {
            "id_lote": request.POST.get('id_lote'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "area": float(request.POST.get('area')),
            "cantidad": int(request.POST.get('cantidad')),
            "estado": request.POST.get('estado'),
            "eventosRecoleccion": request.POST.getlist('eventosRecoleccion'),
            "suministros": request.POST.getlist('suministros'),
            "mantenimientos": request.POST.getlist('mantenimientos')
        }
        url_api = "http://127.0.0.1:8001/lotes"
        try:
            response = requests.post(url_api, json=datos)
            if response.status_code == 200:
                messages.success(request, "Lote registrado")
                return render(request, 'lote.html', {'lote': datos, 'respuesta_api': response.json()})
        except requests.exceptions.ConnectionError:
            messages.error(request, "La API no está encendida")
    return render(request, 'lote.html')



##Vistas
@admin_required
def vista_admin(request):
    return render(request, 'vista_admin.html')

@propietario_required
def vista_propietario(request):
    return render(request, 'vista_propietario.html')

@recolector_required
def vista_recolector(request):
    return render(request, 'vista_recolector.html', {
        "fk_persona": request.session.get("fk_persona") or "",
    })

@recolector_required
def perfil_recolector(request):
    doc = (request.session.get("fk_persona") or "").strip()
    if not doc:
        messages.error(request, "No hay persona asociada a este usuario.")
        return redirect("/")
    if request.method == "POST":
        # Solo permite cambiar datos personales (no documento)
        try:
            actualiza = json.loads(request.body or "{}")
        except Exception:
            actualiza = {}
        actualiza.pop("documento_persona", None)
        actualiza.pop("documento", None)
        try:
            url_api = f"http://127.0.0.1:8001/corregirRegistro/persona/{doc}"
            r = requests.patch(url_api, json=actualiza)
            if r.status_code == 200:
                return JsonResponse({"status": "success"})
            return JsonResponse({"status": "error", "message": r.text or "Error API"}, status=400)
        except Exception:
            return JsonResponse({"status": "error", "message": "Error de conexión"}, status=500)

    # GET
    try:
        url_api = f"http://127.0.0.1:8001/consultarRegistro/persona/{doc}"
        r = requests.get(url_api)
        persona_data = r.json() if r.status_code == 200 else {}
    except Exception:
        persona_data = {}
    return render(request, "perfil_recolector.html", {"volver_url": "/vista_recolector/", "persona": persona_data})


@admin_or_propietario_required
def tipo_insumo_page(request):
    return render(request, 'tipo_insumo.html', {"volver_url": _volver_url(request)})


@admin_or_propietario_required
def unidad_medida_page(request):
    return render(request, 'unidad_medida.html', {"volver_url": _volver_url(request)})


@admin_or_propietario_required
def metodo_aplicacion_page(request):
    return render(request, 'metodo_aplicacion.html', {"volver_url": _volver_url(request)})