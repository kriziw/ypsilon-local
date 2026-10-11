[English](adding-a-transport.md) | [Español](adding-a-transport.es.md) | [Català](adding-a-transport.ca.md)

# Afegir un altre transport

El client F79D reutilitzable consumeix una interfície estructural deliberadament petita:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes:
        """Envia una trama Runxin crua i retorna una trama Runxin crua."""
        ...
```

Hooks opcionals:

```python
class MyTransport:
    def transact(self, frame: bytes) -> bytes: ...
    def transact_write(self, frame: bytes) -> bytes: ...  # ruta no idempotent
    def invalidate(self) -> None: ...                      # reinicia sessió/framing
    def close(self) -> None: ...                           # allibera recursos
```

Es pot utilitzar sense Home Assistant:

```python
from runxin.client import F79DClient

client = F79DClient(MyTransport(...))
identity = client.read_identity()
state = client.read_state()
```

`F79DClient` és una eina de protocol i no imposa els permisos per model de la integració; l’adaptador HA afegeix aquests bloquejos. Un consumidor independent ha de demostrar compatibilitat de model/rangs i lectura física posterior abans d’escriure. L’exemple anterior només llegeix.

Fora d'aquest repositori, copia/vendoritza el paquet pur `runxin/` o utilitza'l
des d'un checkout del codi. No facis que una integració custom de Home Assistant
importi en runtime una altra integració custom instal·lada.

## Semàntica de lliurament de lectures i escriptures

`transact()` és la ruta ordinària i pot fer reintents limitats per operacions
idempotents, com una consulta d'estat.

`transact_write()` és opcional. S'ha d'implementar quan el transport no pugui
demostrar que una resposta fallida implica que el controlador no ha executat
l'ordre. Una escriptura **no s'ha de reenviar a cegues** després d'un timeout,
sessió trencada o ACK perdut: el controlador físic ja podria haver-la aplicat.
Abans de reintentar cal reconciliar amb una lectura independent.

Si no existeix `transact_write()`, `F79DClient` usa `transact()` per compatibilitat.
Els transports nous amb estat haurien d'oferir la ruta específica d'escriptura.

## Què ha de retornar el transport

Ha de retornar la **trama Runxin crua**, començant per `5A 5C`. No ha de retornar:

- un paquet BroadLink xifrat;
- el prefix TFB del BL3372;
- framing sèrie/TCP propi de l'adaptador;
- diccionaris ja descodificats.

El transport elimina el seu propi embolcall abans de retornar la resposta a
`F79DClient`.

## Transports futurs

Poden incloure UART/sèrie directe, bridges TCP, enllaços amb ESPHome o altres
mòduls Wi-Fi. Cap es considera suportat fins que s'hagi validat.

## Proves exigides

Una contribució ha de demostrar com a mínim que:

1. la petició Runxin crua es transmet sense modificar-la;
2. l'embolcall s'afegeix/elimina només a la capa de transport;
3. respostes truncades o malformades fallen de forma segura;
4. els reintents de lectura i reinicis de sessió estan acotats;
5. les escriptures no es dupliquen després d'un lliurament ambigu;
6. `runxin/` continua lliure d'imports específics del transport.

La validació amb maquinari real s'ha de documentar separadament. No s'ha
d'activar descobriment automàtic d'una nova família fins entendre bé la seva
identitat i els possibles falsos positius.
