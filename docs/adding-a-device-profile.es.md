[English](adding-a-device-profile.md) | [Español](adding-a-device-profile.es.md) | [Català](adding-a-device-profile.ca.md)

# Añadir otro perfil de dispositivo Runxin

No copies la tabla F79D cambiándole el nombre. Trata otro controlador como no verificado hasta que las lecturas demuestren qué se comparte. Un controlador compatible puede reutilizar el perfil de protocolo con política propia; compartir tramas no demuestra semántica física idéntica.

## Política de controlador y perfil de protocolo

Si el mapa compartido está demostrado, reutiliza el códec y añade un `ControllerModel` con evidencia, permisos explícitos, incertidumbre y entidades aplicables. `allowed_write_fields` está vacío por defecto. Una Alpha de lectura puede mostrar referencias provisionales, pero debe bloquear reloj, servicios y escrituras directas y desactivar estadísticas provisionales.

Las diferencias demostradas necesitan overrides/fixtures por modelo sin alterar G6/Midnight. Otro mapa requiere perfil/selector explícitos; `protocol_profile` todavía no es una fábrica genérica. Prueba campos ausentes, códigos desconocidos, intentos de eludir permisos, reinicios e identidades existentes.

Consulta la [política de soporte](model-support.md) y el [modelo 1](model-1-alpha.es.md).


## Flujo de trabajo recomendado

1. Identifica por separado el controlador/modelo y el transporte.
2. Captura primero tráfico de solo lectura.
3. Confirma si el formato de trama sin procesar coincide con `runxin/framing.py`.
4. Determina el campo de modelo/identidad y un conjunto mínimo y seguro de lectura.
5. Crea un catálogo declarativo de campos con codecs y evidencia explícitos.
6. Añade pruebas offline con tramas de referencia y regresión.
7. Solo entonces investiga escrituras, campo a campo, con lectura física posterior.
8. Mantén los controles de Home Assistant más restringidos que la capacidad teórica de escritura del protocolo hasta comprender rangos y consecuencias.

## Reutilizar el framing compartido

Si el nuevo dispositivo usa la misma envolvente `5A 5C` / `DF FD` y los mismos opcodes de petición/respuesta, reutiliza `runxin/framing.py`. Si no, añade una implementación de framing separada en vez de relajar la validación para aceptar formatos de paquete no relacionados.

## Catálogo de campos

Usa `FieldSpec` / `FieldCodec` de `runxin/fields.py` como patrón. Conserva:

- id de campo;
- nombre semántico estable;
- codec de lectura;
- codec de escritura conocido, si existe;
- notas de unidad/escalado;
- procedencia/evidencia.

No ocultes la incertidumbre. `inferred` es preferible a presentar una hipótesis como un hecho de protocolo verificado.

## El soporte en Home Assistant es una decisión separada

Un perfil reutilizable puede existir en el repositorio antes de que la integración Runxin Local lo soporte. Añadirlo al descubrimiento automático/config flow requiere trabajo adicional: nombre del modelo, identidad del dispositivo, aplicabilidad de entidades, política de escrituras seguras, traducciones, diagnósticos y pruebas con hardware real.

Esta separación permite que el trabajo de ingeniería inversa sea útil sin fingir que un modelo nuevo está listo para producción.

## Higiene de la evidencia

Aporta capturas saneadas, tablas de campos decodificadas y fixtures de prueba escritos de forma independiente. No subas APK del fabricante, firmware, volcados de código descompilado, claves privadas, credenciales ni secretos.
