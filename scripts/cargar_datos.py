"""Carga el catálogo de la demo en productos-service (15 productos con su stock). Es idempotente: si ya hay productos, no hace nada.

Solo usa la biblioteca estándar; corre dentro de un contenedor (ver docker-compose.yml, servicio "cargador").
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://productos:8080/api/productos"


def pedir(metodo, url, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return json.load(respuesta)


def main():
    existentes = pedir("GET", BASE + "?size=1")
    if existentes.get("totalElementos", 0) > 0:
        print("El catálogo ya tiene productos: no se carga nada.")
        return 0
    with open("/datos/datos-productos.json", encoding="utf-8") as archivo:
        productos = json.load(archivo)["productos"]
    for producto in productos:
        stock = producto.pop("stockInicial")
        creado = pedir("POST", BASE, producto)
        pedir("POST", f"{BASE}/{creado['id']}/stock/ingresos", {"unidades": stock})
    print(f"Catálogo cargado: {len(productos)} productos con stock.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, KeyError, ValueError) as error:
        print(f"No se pudo cargar el catálogo: {error}", file=sys.stderr)
        sys.exit(1)
