# Semántica de los ajustes F79D recuperados

Este documento recoge los ajustes recuperados de la pantalla avanzada de la antigua WaterDevice y deja explícita su representación en Home Assistant. Complementa `f79d.es.md`; que el códec pueda codificar un campo no implica que sea seguro exponerlo como control de escritura.

## Campos enum

| Campo | Nombre de protocolo | Valores brutos | Estados de Home Assistant | Política HA |
|---:|---|---|---|---|
| 2 | `language` | 0 chino, 1 inglés, 2 español, 3 francés, 4 ruso, 5 italiano, 6 alemán, 7 polaco | `chinese` … `polish` | enum de diagnóstico, deshabilitado por defecto |
| 3 | `deviceTimeScheme` | 0 12 horas, 1 24 horas | `12_hour`, `24_hour` | enum de diagnóstico, deshabilitado por defecto |
| 24 | `outRelayMode` | 0 `b-01`, 1 `b-02` | `b_01`, `b_02` | enum de diagnóstico, deshabilitado por defecto |
| 48 | `absorbSaltMode` | 0 aspiración inversa (`逆吸`), 1 aspiración directa (`顺吸`) | `reverse`, `forward` | enum de diagnóstico, deshabilitado por defecto |

Las claves de estado estables de Home Assistant no utilizan texto traducido. El código bruto original se conserva en el atributo `raw_code` de la entidad.

## Evidencia del idioma del controlador (2.9.3)

La fila anterior es la **tabla DeviceLanguage de referencia**, no un mapa universal de los controladores locales. La [definición de la API del fabricante](https://api.waterdevice.net/api/abp/api-definition?includeTypes=true) asocia `DeviceProtocolDataDto.Language` con `Devices.Protocols.DeviceLanguage`; el idioma de cuenta/app utiliza otros enums (`Identity.LanguageType` / `LanguageVersion`). El frontend examinado vincula los selectores de dispositivo y cuenta por separado. Una coincidencia de códigos no demuestra que se pueda sustituir una tabla por otra.

| Modelo | Código del campo 2 | Referencia | Idioma confirmado en pantalla |
|---|---|---|---|
| 1, issue #17 | 7 | Polaco | Neerlandés |
| 9, Ypsilon G6 del proyecto | 3 | Francés | Español |

La [respuesta de la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) confirma neerlandés. Los diagnósticos del G6 indican modelo 9/código 3 y sus menús físicos están en español. `device_language_keys()` aplica solo esas correspondencias, con opciones enum traducidas y `raw_code` conservado. Los modelos 12/14 y los demás códigos mantienen la referencia. Una lectura ausente sigue unknown y un código desconocido se muestra en decimal. No se expone escritura de idioma.

No se ha demostrado la causa de la discrepancia local/referencia. El firmware BroadLink 62016 es el del módulo Wi-Fi; no demuestra que dos válvulas compartan firmware ni tabla de idiomas.

El sensor de idioma también informa `controller_model` e `interpretation` (`controller_display_confirmed` o `reference_device_language_enum`) para distinguir etiquetas observadas de las de referencia.

## Campos numéricos recuperados de la misma UI

| Campo | Nombre de protocolo | Rango WaterDevice | Representación HA |
|---:|---|---:|---|
| 13 | `washingIncreaseNumber` | 0–20 | sensor de diagnóstico de solo lectura, deshabilitado por defecto |
| 14 | `backWashIntervalNumber` | 0–20 | sensor de diagnóstico de solo lectura, deshabilitado por defecto |
| 25 | `regenerationAlarmNumber` | 5–1200 | sensor de diagnóstico de solo lectura, habilitado por defecto |

WaterDevice etiqueta el campo 25 como el recuento de regeneraciones usado para el recordatorio. En el Ypsilon G6 probado el valor observado es 700. Es útil como umbral nativo para calcular el mantenimiento de la resina; **no** es el contador actual de regeneraciones.

## Ajustes de escritura existentes: límites recuperados de la UI

WaterDevice limita el campo 6 (`continuousWaterTime`) a 0–120 minutos. Home Assistant replica este rango.

El campo 7 (`flowRateOff`) depende de la unidad. La integración solo habilita el `number` escribible para la familia validada en metros cúbicos (código de unidad 2), donde WaterDevice limita la visualización a 10,00 m³/h. El protocolo almacena centésimas, por lo que el rango bruto seguro correspondiente es 0–1000.

Los demás límites de escritura expuestos se mantienen:

- campo 43 `saltAddition`: 0–100 kg;
- campo 47 `rawWaterHardness`: 50–1500 mg/L.

Estos rangos de la UI son independientes de la política de evidencia de escritura. En el Ypsilon G6 probado, el campo 7 está `HARDWARE_WRITE_VERIFIED` con un valor de 16 bits **big-endian**. La lectura decisiva es `03 E8`, que corresponde a raw 1000 / 10,00 m³/h; versiones anteriores del proyecto con BE ya habían completado correctamente la escritura y el read-back locales. La regresión LE de la 2.6.x producía `593,95 m³/h` con esos mismos bytes y fallaba la confirmación estricta de escritura.

## Fuente de la evidencia

Los mapeos de enums de referencia y rangos de UI proceden de la configuración y de los módulos recuperados del JavaScript de la antigua WaterDevice. Para el orden de bytes del campo 7 prevalece la evidencia física del G6 cuando entra en conflicto con la interpretación del códec antiguo. `tests/test_recovered_settings_semantics.py`, `tests/test_f79d.py` y `scripts/audit.py` lo protegen contra regresiones; las traducciones siguen completas en inglés, castellano y catalán.
