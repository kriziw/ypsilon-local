[English](hardware-verification.md) | [Español](hardware-verification.es.md) | [Català](hardware-verification.ca.md)

# Verificación de escrituras sobre hardware

Un campo solo se marca `HARDWARE_WRITE_VERIFIED` cuando la integración local ha probado toda la ruta de escritura y lectura posterior contra un controlador físico. Un ACK o un códec autoconsistente no son suficientes.

La corrección del modo vacaciones en la 2.6.1 sigue siendo un ejemplo deliberado de esta regla: el campo 49 es codificable según la aplicación antigua, pero el G6 probado respondió con ACK a la escritura local directa sin cambiar el estado en lecturas frescas. Por eso Home Assistant expone el estado de vacaciones únicamente como lectura.

## Secuencia requerida

Para un campo de configuración reversible:

1. **GET inicial** — leer el valor actual localmente.
2. **SET candidato** — enviar una única escritura con el códec que se quiere validar.
3. **GET independiente** — volver a consultar físicamente el controlador.
4. **Validación física/semántica** — confirmar que el estado observado significa lo esperado.
5. **Restauración** — volver a escribir el valor inicial.
6. **GET de restauración** — verificar que el estado original se ha recuperado.

No se debe utilizar estado cacheado del coordinator como evidencia. Para una acción mecánica también debe comprobarse la fase o transición física esperada.

## Entrega ambigua

Si el SET ya se ha enviado pero se pierde la respuesta o hay timeout, **no se reenvía a ciegas**. El controlador podría haberlo ejecutado. Primero debe hacerse un GET nuevo y reconciliar el estado físico.

## Niveles de evidencia

- códec de la app → `LEGACY_APP_CODEC`;
- valor observado en el dispositivo → `DEVICE_STATE_OBSERVED`;
- cambio observado en cloud → `CLOUD_WRITE_OBSERVED`;
- SET local + lectura física independiente completa → `HARDWARE_WRITE_VERIFIED`.

## Estado actual Ypsilon G6 / F79D

Verificados localmente de extremo a extremo:

- campo 4 — reloj / sincronización;
- campo 6 — límite de consumo continuo;
- **campo 7 — umbral de cierre por caudal, u16 big-endian**;
- campo 10 — hora de regeneración;
- campo 43 — cantidad de sal añadida;
- campo 47 — dureza del agua de entrada.

Pendientes o deliberadamente no verificados:

- **campo 34** — escrituras mecánicas/máquina de estados más allá del comportamiento específico ya probado;
- **campo 49** — el control local directo `1/0` de vacaciones está explícitamente no verificado en el G6 probado y no se expone como control de HA.

## Evidencia del campo 7

El G6 físico resuelve el orden de bytes del campo 7 independientemente de la interpretación de la aplicación antigua:

```text
bytes en el cable: 03 E8
big-endian:    0x03E8 = 1000 -> 10,00 m³/h
little-endian: 0xE803 = 59395 -> 593,95 m³/h
```

La app oficial mostraba 10,00 m³/h mientras Ypsilon 2.6.2, con la regresión LE, mostraba 593,95 m³/h. La vía de escritura aporta una segunda prueba: 2,00 m³/h son raw 200 (`0x00C8`) y deben enviarse como `00 C8`; la regresión LE enviaba `C8 00`, recibía ACK pero el read-back físico no cambiaba y el coordinator generaba `Write ACKed but not confirmed`.

Versiones anteriores del proyecto con BE ya habían completado correctamente el SET/read-back físico del campo 7. Sumando aquella verificación a la evidencia actual independiente, el campo 7 vuelve a estar `HARDWARE_WRITE_VERIFIED`. La discrepancia con el códec antiguo se conserva documentada, pero para el G6 probado prevalece el controlador real.

## Evidencia del fallo del campo 49

La UI antigua modela la entrada en vacaciones desde station 0, la progresión `0 -> 3 -> 7 -> 2 -> 8` y el estado estable como campo 49 verdadero + station 8. En el G6 probado, sin embargo, un SET local directo del campo 49 recibió ACK y lecturas locales independientes repetidas siguieron devolviendo `vacationPattern=false` hasta el timeout. Por tanto ese método concreto no funciona en el hardware probado y Ypsilon no inventa una secuencia mecánica alternativa.

## Evidencia de agua y sal

El histórico real confirma que `dailyWaterConsumption` aumenta durante el día y se reinicia al cambiar de día, lo que respalda `TOTAL_INCREASING` para el campo 37. Las capturas de la app oficial muestran que el campo 39 no es la misma magnitud que las barras de totales semanales históricos, por lo que los campos 39 y 41 no tienen `state_class`.

El campo 43 tiene SET/read-back local verificado y cambio observado por cloud. Su semántica es «sal añadida» en kg, no un sensor físico de nivel.

## Euro-Clear Midnight / modelo de controlador 12

**Soporte experimental / Alpha, limitado al modelo 12 y probado inicialmente con Midnight 25.** Los controles siguen disponibles para validarlos y conservan el read-back estricto; este estado no certifica las órdenes pendientes. La evidencia del G6 no se transfiere automáticamente al modelo 12. El catálogo compartido `FieldSpec` describe la evidencia del G6 de referencia; la evidencia por modelo está en `models.py` y en los diagnósticos.

Hardware: Euro-Clear Midnight 25 (cabezal ECOPRO+) con módulo BroadLink BL3372 (devtype `0x520F`), que informa `deviceModel` 12. Probado el 2026-10-04 con la válvula en servicio y vacaciones desactivado.

Una lectura completa de los campos 1–52 se decodifica de forma coherente con el mapa F79D y la pantalla del controlador. Diferencias: el campo 26 informa décimas de litro (250 en una unidad de 25 L), y los campos 24 (valor 2) y 9 (valor 255) quedan fuera de los enums recuperados.

Verificado localmente de extremo a extremo (GET base → un SET → GET nuevo → restauración → GET nuevo, sin efectos secundarios en otros campos): campo 43 `saltAddition` 23 → 24 → 23, campo 10 `regeneratingTriggerTime` 00:00 → 00:01 → 00:00, campo 6 `continuousWaterTime` 0 → 120 → 0 y campo 4 `currentTime` (sincronización 16:31 → 16:32).

Aún sin verificación física en el modelo 12: campo 7 (`flowRateOff`, lee `00 C8` = 2,00 m³/h en big-endian), campo 47 (`rawWaterHardness`) y la regeneración forzada del campo 34.

`FA 00` del campo 26 confirma la visualización actual de 25 L en Midnight 25; no determina el significado del segundo byte ni el códec de volúmenes mayores. Se conservan U8 y la escala 0,1, y `_raw_resinVolumeBytes` guarda los dos bytes para investigarlos.

### Investigación de los enums y la dureza del modelo 12 (2026-10-05)

Se han consultado el [manual del fabricante Euro-Clear Midnight (2025)](https://euro-clear.eu/shop/wp-content/uploads/2025/11/2025_Midnight_gepkonyv_HU.pdf) y el [manual Runxin F105/F136](https://manufacturervalve.com/pdf/download-center_22.pdf). No establecen una correspondencia del campo 9 con valor 255 ni del campo 24 con valor 2 con una etiqueta. El modelo físico de válvula o un menú no equivale automáticamente al código del controlador BroadLink ni a un enum del protocolo. Se muestran los códigos decimales `255` y `2` y se conserva `raw_code` hasta obtener evidencia específica. Los datos ausentes siguen siendo `unknown`; las etiquetas conocidas se conservan.

[WaterCare 0.6.0](https://github.com/kriziw/Euroclear-broadlink/tree/2b5b5076e6131d96d98b2263e1f7ee47ce388db7) reutiliza nuestro mapa y también muestra estos códigos sin interpretar. Es evidencia de interoperabilidad, no una confirmación independiente del significado. El contribuyente indica que WaterDevice no se conecta a esta unidad; comparar con la pantalla física y con una lectura HA nueva es útil sin exigir una app del fabricante que no funciona.

El manual Midnight, página impresa 16, indica multiplicar la dureza alemana medida (nk°) por 10 (15 → 150 mg/L); en otro apartado (página 7) expresa la dureza del agua como CaO mg/L. Esta convención ayuda a comparar lecturas del modelo 12. Se conservan el valor comunicado, la unidad HA mg/L y el rango de escritura; no se aplica ninguna conversión silenciosa ni se generaliza esta convención al G6.

### Validaciones pendientes

- Campos 7 y 47: GET inicial → un SET adecuado → GET nuevo → comparación con pantalla/app → restauración → GET nuevo. Incluir ambos bytes, el valor solicitado y cualquier error de confirmación.
- Campo 26: informar de ambos bytes y del volumen de resina mostrado en pantalla/app. No se necesita otra unidad; los volúmenes mayores quedan pendientes hasta obtener evidencia.
- Durante una regeneración prevista, comprobar que el botón HA inicia el ciclo físico y que las fases leídas coinciden. El avance de fase es una acción pendiente separada; no hace falta saltar fases para completar estas pruebas.
- Confirmar 25 L en HA, los códigos decimales `2`/`255` con `raw_code` para los enums sin correspondencia y posibles errores recurrentes durante el uso normal.

Los resultados parciales son útiles. Incluir modelo, firmware, fecha, valores iniciales/restaurados y diagnósticos anonimizados; omitir MAC, IP y credenciales. Estas pruebas no se consideran completadas hasta que un contribuyente informe de ellas.

## Campo 52

El campo 52 queda intencionadamente fuera del bloque normal 1..51. La capa Ypsilon lo consulta y cachea por separado porque es un intervalo de servicio que cambia lentamente.

## Regla de generalización

La evidencia de un controlador o firmware no debe generalizarse automáticamente a todos los dispositivos Runxin. Antes de ampliar soporte a otro transporte, rebrand o firmware, deben verificarse de forma independiente el códec y el comportamiento físico.

Consulta también [`waterdevice-audit.es.md`](waterdevice-audit.es.md).

## Controlador sin marca modelo 1 / F150: reloj confirmado

La [respuesta del 10-10-2026 en la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) informa valor inicial 11:23, escrituras manuales desde HA a 11:24 y 11:26 y restauración mediante sincronización manual. Pantalla y Water Device coinciden en cada paso. Se registra **campo 4, reloj/sincronización manuales verificados** en esa unidad (firmware BL3372 62016); los campos 6/10/34/43/47 siguen pendientes. La 2.9.3 habilita únicamente los controles manuales verificados del campo 4 por defecto. Los demás conservan las opciones explícitas; se mantienen sensores de referencia y corrección automática bloqueada.

El código de idioma 7 es neerlandés en pantalla. El G6 modelo 9 del proyecto devuelve código 3 con menús en español; consulta [las correspondencias limitadas por modelo](f79d-settings.es.md). No valida todo el enum ni el idioma de app/cuenta.

Resina raw 240 y referencia por ciclo 15 son lecturas diferentes sin conversión confirmada. El usuario modificó 24 → 15 bajo la etiqueta Water treatment capacity de la app antigua; faltan unidad y correspondencia exacta con el campo local. Los 24 L nominales hacen plausible una escala 0,1 pero no confirman el parámetro configurado. No hace falta repetir reloj/diagnósticos ni aplicar el códec del modelo 14. [Guía del modelo 1](model-1-alpha.es.md).

### Funcionamiento del modelo 1 y observación de una fase con 2.9.3

La [respuesta posterior de la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirma consultas periódicas normales, recuperación tras reiniciar HA y coincidencia con la pantalla en aspiración de salmuera / enjuague lento ascendente. No valida todas las fases ni las duraciones configuradas: se excluyen los intentos abortados y la observación aproximada del llenado se hizo con consultas cada 60 segundos. La opción de regeneración de HA estaba desactivada; la escritura del campo 34 sigue pendiente.

HA mostró capacidad restante 3429 L tras el ciclo, manteniendo resina cruda 240 y referencia por ciclo 15. Son lecturas reportadas y una comprobación de coherencia, no una confirmación independiente de la escala de resina o las unidades de capacidad. La etiqueta L del ajuste antiguo se recuerda con incertidumbre. Alpha y escrituras pendientes se mantienen; no se piden más pruebas ni informes al contribuyente. La incidencia original de conexión/alta puede cerrarse independientemente. [Registro detallado](model-1-alpha.es.md#funcionamiento-reportado-después-de-regenerar-con-293).

## Euro-Clear Midnight / controlador modelo 14 (F136)

**Beta en 2.9.2**, contrastada en Euro-Clear Midnight 25 Plug&Play / F136 / ECOPRO+, BL3372 `0x520F`, firmware **62016**. La [issue #22](https://github.com/Danirv/runxin-local/issues/22) confirma funcionamiento con 2.9.1 tras actualizar/reiniciar, sin modificar modelos localmente. Las lecturas **4/6/7/10/43/47** coinciden con la app (campo 7: 3,5 m³/h; campo 47: 260 mg/L). Las escrituras **4/6/10/43** están verificadas por el usuario; **las escrituras 7/47 y las acciones mecánicas de 34 siguen pendientes**.

El campo 26 `[44, 1]` coincide en diagnósticos e informe independiente de lectura. La [foto del controlador](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) muestra **30,0 L** configurados. U16 little-endian da `0x012C = 300`, con escala 0,1 para obtener 30,0 L. La 2.9.2 aplica la excepción solo al modelo 14 y marca `resin_volume_scale_confirmed=true`; G6/modelo 12 mantienen sus códecs. Los 25 L nominales son distintos del parámetro configurado; no se cambia ningún ajuste. Es una comparación de bytes reportados y pantalla, no una trama completa capturada ni una nueva prueba de escritura del mantenedor. No hace falta otra comparación de resina ni repetir el informe. [Guía del modelo 14](model-14-alpha.es.md).
