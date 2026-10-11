[English](adding-a-transport.md) | [Español](adding-a-transport.es.md) | [Català](adding-a-transport.ca.md)

# Añadir otro transporte

El cliente F79D reutilizable usa una interfaz estructural deliberadamente pequeña:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes:
        """Envía una trama Runxin cruda y devuelve una trama Runxin cruda."""
        ...
```

Hooks opcionales:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes: ...
    def transact_write(self, frame: bytes) -> bytes: ...  # ruta no idempotente
    def invalidate(self) -> None: ...                      # reinicia sesión/framing
    def close(self) -> None: ...                           # libera recursos
```

Puede usarse sin Home Assistant:

```python
from runxin.client import F79DClient

client = F79DClient(MyTransport(...))
identity = client.read_identity()
state = client.read_state()
```

`F79DClient` es una herramienta de protocolo y no impone los permisos por modelo de la integración; el adaptador HA añade esos bloqueos. Un consumidor independiente debe demostrar compatibilidad de modelo/rangos y lectura física posterior antes de escribir. El ejemplo anterior solo lee.

Fuera de este repositorio, copia/vendoriza el paquete puro `runxin/` o úsalo
desde un checkout del código. No hagas que una integración custom de Home
Assistant importe en runtime otra integración custom instalada.

## Semántica de entrega de lecturas y escrituras

`transact()` es la ruta normal y puede usar reintentos limitados para operaciones
idempotentes, como una consulta de estado.

`transact_write()` es opcional. Debe implementarse cuando el transporte no pueda
demostrar que una respuesta fallida significa que el controlador no ejecutó la
orden. Una escritura **no debe reenviarse a ciegas** después de un timeout,
sesión rota o ACK perdido: el controlador físico podría haberla aplicado. Antes
de reintentar hay que reconciliar mediante una lectura independiente.

Si no existe `transact_write()`, `F79DClient` usa `transact()` por compatibilidad.
Los nuevos transportes con estado deberían proporcionar la ruta específica de escritura.

## Qué debe devolver el transporte

Debe devolver la **trama Runxin cruda**, empezando por `5A 5C`. No debe devolver:

- un paquete BroadLink cifrado;
- el prefijo TFB del BL3372;
- framing serie/TCP propio del adaptador;
- diccionarios ya decodificados.

El transporte elimina su propio envoltorio antes de devolver la respuesta a
`F79DClient`.

## Transportes futuros

Pueden incluir UART/serie directo, bridges TCP, enlaces mediante ESPHome u otros
módulos Wi-Fi. Ninguno se considera soportado hasta validarlo.

## Pruebas exigidas

Una contribución debe demostrar al menos que:

1. la solicitud Runxin cruda se transmite sin alterarla;
2. el envoltorio se añade/elimina solo en la capa de transporte;
3. respuestas truncadas o malformadas fallan de forma segura;
4. los reintentos de lectura y reinicios de sesión están acotados;
5. las escrituras no se duplican tras una entrega ambigua;
6. `runxin/` sigue libre de imports específicos del transporte.

La validación con hardware real debe documentarse por separado. No se debe
activar descubrimiento automático de una nueva familia hasta entender bien su
identidad y los posibles falsos positivos.
