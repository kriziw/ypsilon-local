[English](CONTRIBUTING.md) | [Español](CONTRIBUTING.es.md) | [Català](CONTRIBUTING.ca.md)

# Contribuir

Las contribuciones son bienvenidas. El proyecto prioriza control local fiable, reconciliación explícita del estado, escrituras mecánicas conservadoras y conocimiento de interoperabilidad reutilizable.

## Antes de abrir un pull request

1. Instala `requirements-test-offline.txt` en un entorno Python aislado y ejecuta `python -m pytest -q`, `python scripts/audit.py` y `python scripts/field_surface_audit.py`.
2. Ejecuta `python scripts/publication_check.py` en un clon público configurado.
3. Ejecuta `python -m compileall -q custom_components/ypsilon_local scripts tests`.
4. Mantén los textos visibles para el usuario en los archivos de traducción (`en`, `es`, `ca`).
5. Prefiere cambios pequeños y revisables y conserva los unique ids de entidades/config entries salvo que exista una migración.
6. En escrituras, distingue transporte del comando, ACK de protocolo y estado físico confirmado.

## Límites de arquitectura

La CI principal mantiene ligeras las pruebas de protocolo. Para probar config
flow, entidades y controles con clases reales de Home Assistant, usa Python
3.14, instala `requirements-test-ha.txt` y ejecuta
`python -m pytest -q`.
Estas pruebas simulan la E/S del dispositivo y no establecen evidencia física.

Lee [`docs/architecture.es.md`](docs/architecture.es.md) antes de trabajar con el protocolo.

- `runxin/` debe seguir siendo independiente de Home Assistant y BroadLink.
- Los transports transportan tramas Runxin en bruto y no deben decodificar campos F79D.
- Paquetes, cifrado y sesión pertenecen a la implementación del transport.
- IDs de campo, codecs y evidencia pertenecen al perfil de dispositivo.
- Home Assistant decide qué escrituras conocidas son seguras de exponer.
- `protocol.py` es una fachada de compatibilidad, no el lugar para lógica nueva.

El trabajo nativo ejecuta toda la suite con HA 2026.9.4; otro usa `requirements-test-ha-baseline.txt` con HA 2026.9.3. Son versiones probadas con E/S simulada, no una versión mínima declarada.

Las revisiones del código de las acciones están fijadas, pero HACS/hassfest aún utilizan etiquetas de contenedores que pueden cambiar. Esto no fija toda la cadena de herramientas. Las comprobaciones de imports son estáticas; no aíslan el código durante la ejecución.

Para un modelo compatible nuevo, reutiliza el mapa compartido, documenta la incertidumbre de unidades/aplicabilidad y empieza con permisos de escritura vacíos. Las pruebas Alpha deben cubrir bloqueos de reloj, servicios y adaptador, y conservar identidades y conversiones del G6/modelo 12. Una familia de protocolo distinta necesita evidencia y perfil propios. Consulta la [matriz de soporte](docs/model-support.md) y la [guía de verificación física](docs/hardware-verification.es.md).

## Investigación del protocolo y datos de prueba

No publiques APK del fabricante, firmware, scripts/binarios propietarios, credenciales, claves privadas o de emparejamiento, tokens de cuenta ni capturas sin sanear con identificadores de usuario/dispositivo.

Los fixtures pequeños y saneados necesarios para probar código escrito de forma independiente son aceptables si no contienen secretos ni partes sustanciales de código/contenido del fabricante.

Al documentar un hecho de ingeniería inversa, diferencia evidencia recuperada de la app antigua, comportamiento observado en un dispositivo real, una escritura físicamente verificada y una inferencia. Es preferible marcar algo como `inferred` que presentarlo como certeza falsa.

## Nuevos transports

Consulta [`docs/adding-a-transport.es.md`](docs/adding-a-transport.es.md). Un transport debe implementar el contrato `transact(frame: bytes) -> bytes` y retirar únicamente su propia envolvente antes de devolver la respuesta.

## Nuevos dispositivos Runxin

Consulta [`docs/adding-a-device-profile.es.md`](docs/adding-a-device-profile.es.md). Incluye marca/modelo, controlador/válvula, identidad del transport/módulo si se conoce y qué campos/comandos se han verificado realmente.

## Posible librería independiente

La capa pura de protocolo está preparada para poder extraerse más adelante a una librería pública de PyPI si aparecen varios consumidores reales. Hasta entonces, no introduzcas dependencias runtime entre integraciones HACS importando un `custom_components.ypsilon_local` instalado.

## Licencia

Al contribuir aceptas que tu contribución se publica bajo la licencia Apache 2.0 del repositorio.
