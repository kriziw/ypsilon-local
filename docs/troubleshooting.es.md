[English](troubleshooting.md) | [Español](troubleshooting.es.md) | [Català](troubleshooting.ca.md)

# Resolución de problemas de conexión

El descubrimiento, la autenticación local y las lecturas F79D son etapas distintas.
Que `broadlink.hello()` funcione no demuestra que el dispositivo acepte control local.

## Mensajes y registros de configuración

Desde 2.7.1, la configuración distingue el rechazo de autenticación (`invalid_auth`),
el rechazo con bloqueo anunciado (`device_locked`) y otros fallos (`cannot_connect`).
El bit de bloqueo es una observación del descubrimiento, no una causa demostrada.
Ypsilon sigue intentando la autenticación normal aunque ese bit sea verdadero.

Un intento fallido emite un aviso con el resultado, la etapa del transporte, el
tipo de excepción, el código numérico, el tipo de dispositivo y el bloqueo anunciado.
No hace falta haber creado una entrada. Para obtener más detalle, activa la
depuración en el menú de la integración o añade esto a `configuration.yaml` y reinicia HA:

```yaml
logger:
  default: warning
  logs:
    custom_components.ypsilon_local: debug
```

Si ya tienes una sección `logger:`, integra esta opción sin duplicarla.
Reproduce un intento, recoge las líneas de Ypsilon y desactiva la depuración.
Los nuevos mensajes omiten IP/MAC, nombres, claves, paquetes y el texto original
de las excepciones. Revisa los demás registros de HA antes de compartirlos.

Para entradas configuradas, descarga los diagnósticos desde el menú de la
integración o dispositivo. `connection.transport` contiene la última etapa,
el tipo descubierto, el bloqueo anunciado y los metadatos del último fallo.
`last_error` se conserva aunque después haya una transacción correcta; `available`
indica el estado actual del coordinador. Si falla la configuración inicial,
todavía no hay entrada para descargar: utiliza el aviso o el script independiente.

## Informe independiente

Desde la raíz del repositorio, en un entorno Python que ya tenga `python-broadlink==1.0.6`,
ejecuta esto sustituyendo `DEVICE_IP` localmente:

```bash
python scripts/debug_connection.py DEVICE_IP
```

El script hace un descubrimiento y una autenticación normal. Si se autentica,
también intenta leer el firmware. No envía órdenes de configuración, bloqueo,
aprovisionamiento ni regeneración y no consulta campos F79D. El JSON incluye
versiones Python/BroadLink, timeout y resultados por etapa; omite dirección, MAC,
nombre, identificador de control, claves, paquetes y texto de las excepciones.
El código de salida 1 indica que la autenticación no tuvo éxito. La lectura de
firmware puede fallar separadamente sin invalidar una autenticación correcta.

Utiliza, si puedes, el mismo entorno Python y de red de la prueba original.
Un complemento Terminal/SSH, HA Core y otro PC pueden tener entornos distintos;
indica desde dónde lo ejecutaste. No sustituyas las dependencias gestionadas por HA.

## Si se rechaza la autenticación

1. Indica si alguna vez funcionó la autenticación local, las versiones de HA y
   de la integración, el nombre/versión de la app y desde dónde haces la prueba.
2. Cierra la app del fabricante y pausa otros clientes locales; ejecuta una prueba nueva.
3. Si la app ofrece una opción de bloqueo/control local, indica su estado.
   Consulta las instrucciones del fabricante antes de modificarla; no sabemos
   si esta opción existe en todos los firmwares de Water Device.

Un bloqueo anunciado junto con rechazo justifica investigar esa hipótesis.
Un bit falso no demuestra que todo el control local esté permitido. La vinculación
con la app no prueba por sí sola que haga falta una clave proporcionada por la nube.

El bloqueo BroadLink está documentado en la [guía de Home Assistant](https://www.home-assistant.io/integrations/broadlink/#device-is-locked)
y en la [discusión upstream #377](https://github.com/mjg59/python-broadlink/issues/377).
Los ejemplos corresponden a otros dispositivos; no son una reparación verificada
para el G6. No restablezcas de fábrica, no elimines la vinculación con la nube
ni envíes un supuesto `set_lock(False)` como primer paso de diagnóstico.

Si persiste el rechazo, se puede acordar una captura limitada a descubrimiento y
autenticación para compararla con un G6 funcional. Acuerda primero la recogida y
anonimización: no publiques PCAPs completos, que pueden contener material de sesión
e identificadores. Esta investigación no requiere escrituras de configuración.

## Solución de emparejamiento reportada en la issue #17

Un usuario con Runxin/润新 iOS 2.0.0 observó bloqueo anunciado y autenticación rechazada. El emparejamiento completo con Water Device 2.1.3 sustituyó el vínculo anterior: bloqueo false y autenticación correcta con la app cerrada. No reportó restablecimiento de fábrica del controlador ni cambios físicos. Después solo una app podía ver/controlar el equipo.

Es un caso documentado, no una regla para todas las versiones. Reemparejar puede reemplazar el vínculo de la app anterior; no es añadir otro cliente. No implementamos claves cloud ni desbloqueo automático. No hace falta repetir el procedimiento en un dispositivo que funciona.

El controlador resultante devuelve código 1; autenticar no confirma identidad G6/modelo 9. [Issue #17](https://github.com/Danirv/runxin-local/issues/17) y [Alpha de lectura](model-1-alpha.es.md).
