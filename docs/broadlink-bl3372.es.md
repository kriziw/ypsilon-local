[English](broadlink-bl3372.md) | [Español](broadlink-bl3372.es.md) | [Català](broadlink-bl3372.ca.md)

# Transporte BroadLink BL3372

`transport/broadlink_bl3372.py` es el transporte concreto usado actualmente por
la integración Home Assistant y está separado deliberadamente del codec F79D.

## Combinación probada

- devtype BroadLink: `0x520F`
- módulo: BL3372
- controlador: Runxin F79D
- comando BroadLink para datos de producto: `0x6A`
- dependencia Python: `python-broadlink==1.0.6`

Probar otro devtype en investigación no significa que esa combinación quede
soportada por Ypsilon.

## Ruta de transacción

```text
trama Runxin cruda
 -> prefijo uint16-le de longitud (TFB)
 -> send_packet(0x6A, ...)
 -> validar respuesta externa BroadLink
 -> descifrar cuerpo
 -> quitar longitud/padding TFB
 -> trama Runxin cruda
```

El transporte nunca decodifica campos F79D.

## Sesión y reintentos de lectura

Se reutiliza una sesión autenticada y las transacciones se serializan. En
lecturas idempotentes:

- respuesta externa `-1` / `-7` después de autenticar: se permite una nueva autenticación;
- `-5`: es empíricamente transitorio en el hardware probado y admite reintentos
  breves, acotados y con jitter;
- los presupuestos de reautenticación y `-5` son independientes.

La causa interna exacta de `-5` **no está demostrada**.

## Escrituras: sin reintento ciego

Las escrituras usan `transact_write()` y se envían **como máximo una vez**. Si se
pierde la respuesta, caduca la sesión o aparece un error después del envío, el
resultado es ambiguo: el F79D podría haber ejecutado ya el SET.

Por ello no se reenvía automáticamente. El coordinador hace un GET local nuevo y
reconcilia el estado físico. Si coincide, la operación se acepta aunque se haya
perdido el ACK; si no, termina como no confirmada. Es especialmente importante
en acciones mecánicas como forzar una regeneración.

## Diagnósticos

Se exponen contadores de reintentos transitorios de lectura, reautenticaciones y
versión de firmware BroadLink cuando se puede leer.

También se conserva la última etapa del transporte, el tipo de dispositivo, el
bloqueo anunciado y el tipo/código de la última transacción fallida. El bit
anunciado no impide intentar la autenticación. El rechazo del handshake inicial
se distingue de los errores externos posteriores y no se reintenta automáticamente.
Los nuevos registros omiten identificadores, claves, paquetes y texto de las
excepciones. Consulta la [guía de conexión](troubleshooting.es.md) para obtener
registros o el informe independiente.

## Sustituir BroadLink

Otro transporte solo debe aceptar y devolver tramas Runxin crudas. TFB, `0x6A`,
cifrado BroadLink y errores externos no forman parte del contrato genérico.

Consulta [`adding-a-transport.es.md`](adding-a-transport.es.md).
