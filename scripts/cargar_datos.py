"""Carga el catálogo de la demo en productos-service (15 productos con su stock). Es idempotente: si ya hay productos, no hace nada.

Escribir en el catálogo exige rol admin, así que primero pide un token a Keycloak con el cliente de servicio "demo-cargador"
(client_credentials, rol admin, definido en keycloak/realm-demo.json). Solo usa la biblioteca estándar; corre dentro de un
contenedor (ver docker-compose.yml, servicio "cargador").
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("PRODUCTOS_URL", "http://productos:8080") + "/api/productos"
TOKEN_URL = os.environ.get("TOKEN_URL", "http://keycloak:8080/realms/supermercado/protocol/openid-connect/token")
CLIENTE = os.environ.get("CLIENTE_ID", "demo-cargador")
SECRETO = os.environ.get("CLIENTE_SECRETO", "demo-cargador-solo-local")  # clave de la demo; el realm de la demo trae la misma
DATOS = os.environ.get("DATOS", "/datos/datos-productos.json")


def pedir(metodo, url, cuerpo=None, token=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return json.load(respuesta)


def obtener_token():
    formulario = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": CLIENTE, "client_secret": SECRETO}
    ).encode()
    peticion = urllib.request.Request(TOKEN_URL, data=formulario, method="POST")
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return json.load(respuesta)["access_token"]


def main():
    existentes = pedir("GET", BASE + "?tamano=1")
    if existentes.get("totalElementos", 0) > 0:
        print("El catálogo ya tiene productos: no se carga nada.")
        return 0
    token = obtener_token()
    with open(DATOS, encoding="utf-8") as archivo:
        productos = json.load(archivo)["productos"]
    for producto in productos:
        stock = producto.pop("stockInicial")
        creado = pedir("POST", BASE, producto, token)
        pedir("POST", f"{BASE}/{creado['id']}/stock/ingresos", {"unidades": stock}, token)
    print(f"Catálogo cargado: {len(productos)} productos con stock.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, KeyError, ValueError) as error:
        print(f"No se pudo cargar el catálogo: {error}", file=sys.stderr)
        sys.exit(1)
