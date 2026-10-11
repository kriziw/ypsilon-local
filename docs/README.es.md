# Runxin Local para Home Assistant

Integración local para descalcificadores compatibles con **Runxin F79D + BroadLink BL3372**, con el Ypsilon G6 como hardware de referencia y soporte experimental para Euro-Clear Midnight.

El **modelo 1 / F150** tiene una Alpha de lecturas con reloj manual validado en 2.9.3: sensores periódicos, sin escrituras automáticas, con pruebas manuales opcionales en 2.9.1. Las lecturas son provisionales, sin estadísticas a largo plazo; la resina y la cantidad por ciclo no tienen unidad asumida. [Guia](model-1-alpha.es.md).


En **2.9.3**, el modelo 1 tiene opciones desactivadas por defecto para probar ajustes adicionales 6/10/43/47 y una segunda opción para iniciar una regeneración prevista. Las escrituras manuales del reloj y la restauración mediante sincronización manual (campo 4) están verificadas; las demás siguen pendientes. El reloj automático, el campo 7 y el avance de fases siguen bloqueados. [Instrucciones](model-1-alpha.es.md).

## Correcciones en 2.9.3

Release estable con etiquetas de idioma confirmadas en pantalla: modelo 1/código 7 → neerlandés y G6 modelo 9/código 3 → español. Se conserva la tabla de referencia para los demás códigos/modelos y el código original. El modelo 1 mantiene lecturas Alpha, con reloj y sincronización manuales disponibles sin opción experimental; resina 240 y capacidad de tratamiento 15 siguen siendo parámetros distintos con conversión pendiente. [Evidencia de idioma](f79d-settings.es.md).

## Compatibilidad en 2.9.2

La **2.9.2 es una release estable**. Los modelos 1 / F150 y 12 / F105 siguen Alpha; el **modelo 14 / F136 pasa a Beta**. La issue #22 confirma funcionamiento con 2.9.1, lecturas 4/6/7/10/43/47 coincidentes con la app y resina configurada de **30,0 L** en el controlador: `[44, 1]` son 300 en U16 little-endian, divididos entre 10. La 2.9.2 corrige los 4,4 L mostrados antes. Las escrituras 4/6/10/43 están verificadas; las de 7/47 y las acciones mecánicas de 34 siguen pendientes. Se mantienen el comportamiento G6/modelo 12 y las identidades existentes. [Guía del modelo 14](model-14-alpha.es.md).

## Autodiagnóstico y cambio de nombre: 2.8.0

El proyecto pasa de Ypsilon a **Runxin Local**, con repositorio `Danirv/runxin-local`. Se conservan el dominio, la carpeta, los servicios y los identificadores `ypsilon_local`; el cambio de nombre no requiere volver a añadir dispositivos ni modificar automatizaciones.

Si un controlador no está admitido o falla el alta, puedes preparar un **informe de lectura desde Home Assistant**, sin instalar Python ni editar modelos. Confirma la exploración, guarda la entrada de diagnóstico y descarga los diagnósticos desde su menú. La entrada no activa entidades, controles, consultas periódicas ni correcciones del reloj. Los informes parciales son útiles y no se comparten automáticamente. Hay que eliminar esta entrada antes de añadir el dispositivo normalmente cuando tenga soporte.

La tabla del fabricante asocia 9 con F79D, 12 con F105 y 14 con F136; solo describe los códigos y no amplía los modelos admitidos. Sigue siendo necesario contrastar las conversiones con la app o la pantalla del controlador. Consulta la [guía de informes de compatibilidad](compatibility-report.md).

- Descubrimiento DHCP y configuración manual por IP.
- Lectura local de caudal, consumo diario, capacidad restante, fase de válvula, modo de regeneración, patrón de trabajo y avisos.
- Escrituras con lectura física posterior estricta: un ACK no se considera estado confirmado.
- Controles de dureza, cantidad de sal añadida, protecciones de caudal/tiempo, hora de regeneración, reloj y regeneración forzada; la evidencia física se documenta por campo y modelo.
- Estado de vacaciones solo de lectura; la 2.6.1 retira el switch de vacaciones porque la escritura local directa del campo 49 no quedó confirmada físicamente en el G6 probado.
- Diagnósticos para fases de lavado, disolución de sal, pausa 1, errores, comunicación y mantenimiento.
- Traducciones CA/ES/EN y branding local con icono cuadrado y logotipo horizontal independientes.

El botón de regeneración solo inicia el ciclo tras una lectura nueva que confirme servicio y vacaciones desactivadas, y rechaza peticiones simultáneas. Envía la misma orden una sola vez y comprueba la fase resultante. Los enums sin correspondencia muestran el código decimal y conservan `raw_code`; las etiquetas conocidas se mantienen y los datos ausentes son `unknown`. El reloj admite un minuto de avance dentro de los 60 segundos posteriores a la escritura, también a medianoche, solo si una lectura previa nueva demuestra que el valor del minuto siguiente ha cambiado; la hora de regeneración exige coincidencia exacta.

## Nueva compatibilidad en la 2.7.0

El **Euro-Clear Midnight (controlador modelo 12)** tiene soporte **experimental / Alpha**, probado con un Midnight 25 con cabezal ECOPRO+ y BroadLink BL3372 (`0x520F`). Las capturas coinciden con la pantalla del controlador; las escrituras de los campos 4, 6, 10 y 43 están verificadas físicamente. Los campos 7 y 47 y las acciones mecánicas del campo 34 siguen disponibles para pruebas, pero todavía no están verificados en este modelo.

El modelo 12 conserva el soporte Alpha y los controles existentes. Se conservan los controles y la verificación estricta del PR original; el soporte del G6 no cambia. Los diagnósticos incluyen la evidencia por modelo y los dos bytes originales del campo 26. `FA 00` sigue mostrándose como **25 L**; esta captura no determina el significado del segundo byte ni el códec de volúmenes superiores a 25,5 L.

Consulta las [pruebas pendientes del modelo 12](hardware-verification.es.md#euro-clear-midnight--modelo-de-controlador-12).

## Cambio principal de la 2.6.3

El campo 7 (`flowRateOff`, umbral de cierre por caudal) vuelve a utilizar **u16 big-endian** en lectura y escritura y recupera `HARDWARE_WRITE_VERIFIED`.

La prueba física es directa: el controlador devuelve `03 E8` mientras la app oficial muestra 10,00 m³/h. En BE es raw 1000; en LE se convierte erróneamente en 59395 y Home Assistant mostraba 593,95 m³/h. Para escribir 2,00 m³/h, raw 200 debe enviarse como `00 C8`. La regresión LE enviaba `C8 00`, recibía ACK pero el read-back físico no confirmaba el cambio, y la verificación estricta de Ypsilon lo rechazaba correctamente.

Versiones anteriores del proyecto con BE ya habían verificado físicamente SET/read-back para este campo. La superficie HA se mantiene limitada a 0–10,00 m³/h en la familia de unidad 2 validada.

## Cambios principales de la 2.6.1

- Vacaciones: el campo 49 se sigue leyendo y el sensor `desactivado / preparando / activo` se mantiene, pero no se expone ninguna escritura hasta conocer y verificar físicamente la acción local del firmware actual.
- Consumo diario: se mantiene como contador `TOTAL_INCREASING` que crece durante el día y se reinicia al cambio de día.
- Campo 39: **Consumo semanal medio del controlador**. No es el total semanal de las barras históricas de la app oficial.
- Campo 41: **Capacidad de tratamiento por ciclo**, no un contador de consumo.
- Campo 43: **Cantidad de sal añadida**, un valor de registro/configuración en kg; no es el nivel de sal restante.
- Branding con icono cuadrado, logo horizontal y variantes 2x/dark.

## Estadísticas antiguas de Home Assistant

Versiones anteriores crearon estadísticas de largo plazo para el consumo medio semanal y la capacidad por ciclo cuando todavía declaraban `state_class`. Tras actualizar, Home Assistant puede ofrecer eliminar esas estadísticas obsoletas. Es correcto eliminarlas: esto no elimina la entidad ni el historial normal del Recorder.

## Instalación

Con HACS, añade `https://github.com/Danirv/runxin-local` como repositorio personalizado de tipo **Integration** hasta que quede incorporado al catálogo por defecto. Manualmente, copia `custom_components/ypsilon_local` a `/config/custom_components/ypsilon_local`.

## Consumo de agua

Para consumo acumulado utiliza **Consumo diario**. **Caudal** es una muestra instantánea y puede no reflejar consumos muy cortos entre dos sondeos. Para obtener un total real de la semana en Home Assistant, derívalo del contador diario/estadísticas; no utilices el campo 39 como si fuera el total de la semana actual.

## Problemas de conexión

Consulta la [guía de resolución de problemas](troubleshooting.es.md) para distinguir descubrimiento, autenticación rechazada y lecturas F79D. Incluye registros de depuración y un script que genera un informe sin identificadores ni claves, aunque no puedas completar la configuración en HA.

## Seguridad

La integración puede cambiar parámetros e iniciar movimientos de válvula. No es un controlador de seguridad certificado ni debe ser la única protección contra fugas o inundaciones. Conocer el códec no equivale a verificar la acción física. En la compatibilidad Alpha del modelo 12, los controles pendientes siguen disponibles con esta limitación documentada.

Consulta el [README principal](../README.md), [`waterdevice-audit.es.md`](waterdevice-audit.es.md), [`f79d.es.md`](f79d.es.md), [`hardware-verification.es.md`](hardware-verification.es.md), [SECURITY](../SECURITY.md) y [LEGAL](../LEGAL.md).

Consulta el [índice de documentación](index.md), la [matriz de soporte](model-support.md).
