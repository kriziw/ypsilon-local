# Controlador modelo 1 / F150: lecturas Alpha y reloj manual validado

[English](model-1-alpha.md) | [Català](model-1-alpha.ca.md) | [Español](model-1-alpha.es.md)

**2.9.0** admite el código **1** con sensores de lectura periódica. El fabricante llama a este código **F150**, pero la identidad comercial del equipo de la issue #17 no está confirmada. No es soporte general para cualquier producto F150.

La release de la integración es estable; Alpha describe solo el soporte de este modelo.

1. Instala la versión 2.9.3 o posterior con HACS, o descarga el ZIP de la release y copia solo `custom_components/ypsilon_local` a `/config/custom_components/ypsilon_local`. Conserva una copia de la carpeta anterior y reinicia HA. Esta Alpha conserva el dominio; no requiere migrar a `runxin_local`.
2. Si existe una entrada exclusivamente de diagnóstico del mismo dispositivo, descarga primero su informe y elimina esa entrada antes de añadir el equipo normalmente.
3. Añade **Runxin Local**, introduce la IP y acepta la explicación **Alpha con controles manuales del reloj validados**. Consulta cada minuto por defecto, sin cadencia adaptativa. La corrección automática del reloj queda bloqueada aunque una opción antigua esté activada.
4. Compara los sensores con la app. Puedes habilitar las entidades de diagnóstico que estén desactivadas por defecto. No cambies ajustes para tomar capturas.
5. Descarga los diagnósticos desde el menú de la entrada y adjunta el JSON a la issue existente con algunos valores/capturas, unidades y hora aproximada. La descarga exporta el estado guardado y no inicia otra exploración. Oculta identificadores en las capturas.

En **2.9.3**, el **reloj del dispositivo** y el **botón de sincronización manual** son controles validados disponibles sin activar ajustes experimentales. Conservan sus identificadores y la comprobación con lectura nueva. El alta, las consultas y las recargas no inician escrituras del reloj. Los demás ajustes requieren el modo experimental y la regeneración tiene una segunda opción. Servicios administrativos, coordinador y adaptador imponen los mismos permisos por campo; habilitar el campo 4 no permite otras escrituras ni corrección automática.

Las lecturas numéricas usan interpretaciones **F79D de referencia pendientes de validación con la app**. No generan estadísticas de largo plazo; el historial ordinario puede conservarse. Los atributos y diagnósticos incluyen los dos bytes recibidos por campo (`state._rawFieldBytes`), sin paquetes completos, claves ni sesiones. Recibir zero/false no demuestra aplicabilidad.

Comparaciones prioritarias:

| Campo | Referencia del informe | Pendiente |
|---|---|---|
| 26, resina | `F0 00`, primer byte 240 | HA muestra 240 sin L ni multiplicador asumido. Confirmar valor/unidad reales. |
| 41–42, cantidad por ciclo | 15 | El usuario cambió 24 → 15 en Runxin Advanced → Water treatment capacity. Confirmar unidad y correspondencia con este campo; HA mantiene 15 sin unidad asumida. |
| 35–36, restante | 1304 L | Capacidad restante y unidad, cerca de la hora de lectura. |
| 37–40, diario/media semanal | 215 / 192 L | No confundir media del controlador con total histórico semanal. |
| 47, dureza | 280 mg/L | Etiqueta, valor y escala de dureza. |
| 43, sal añadida | 25 kg | Registro de sal añadida, no nivel físico. |
| 4/5/10 y 6/7/15/17/19/21/23 | Horas, protecciones y duraciones | Contrastar lo que exponga la app sin modificar ajustes. |

El segundo byte de resina se conserva sin deducir un códec U16. El campo 52 se guarda en una caché independiente y puede ser anterior al resto de la instantánea. Si app y HA interfieren, pausa la consulta o desactiva temporalmente la entrada; no hace falta volver a emparejar.

La [issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6044822202) confirma módulo `0x520F`, firmware 62016, autenticación con la app cerrada, código 1 estable y los 52 campos recibidos en dos consultas sin errores. Las tramas de prueba reconstruidas son sintéticas. No se han validado campos superiores al 52; el reloj manual (campo 4) está verificado en la unidad reportada y las demás escrituras siguen pendientes; las futuras conversiones específicas no deben modificar G6/Midnight.

## Confirmaciones incorporadas en 2.9.3

La [respuesta del 10-10-2026](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) confirma reloj inicial 11:23, escrituras a 11:24 y 11:26 y restauración con el botón de sincronización manual. La pantalla del controlador y Water Device coinciden tras cada acción. Solo se probó el campo 4 y después se desactivó la opción experimental. No valida la corrección automática ni otras escrituras.

La pantalla física está en neerlandés con código de idioma 7. HA corrige únicamente esa correspondencia del modelo 1, sin escribir el idioma ni cambiar el de la app; los demás códigos conservan las etiquetas de referencia.

El equipo tiene 24 L nominales de resina, pero el campo 26 sigue `F0 00` (referencia 240) y los campos 41–42 siguen en 15. En el frontend del fabricante, `resinVolume` es Resin volume y `periodicWaterProduction` es Water treatment capacity. No hemos confirmado independientemente qué campo local modificaba esa pantalla de la antigua app Runxin. `240 / 10 = 24 L` es plausible, pero aún no es una comparación con el valor configurado. Se conservan ambas lecturas sin unidad asumida y no se aplica el códec U16 del modelo 14.

El volumen de resina debe describir la carga real, no adaptarse al número de personas. La capacidad de tratamiento es otro parámetro que depende de resina, dureza y ajustes de regeneración; reducirla manteniendo los ciclos puede hacer regenerar más a menudo en lugar de ahorrar. Hay que aclarar etiqueta/unidad y seguir las instrucciones del equipo antes de proponer un cambio. No hace falta volver a emparejar, recuperar la app antigua, repetir diagnósticos ni modificar ajustes para aclarar las lecturas.

## Funcionamiento reportado después de regenerar con 2.9.3

La [respuesta posterior del 10-10-2026](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirma consultas periódicas normales y recuperación de las lecturas tras reiniciar HA después de las actualizaciones. La unidad reporta modelo 1, firmware BL3372 62016 e integración 2.9.3.

A las 19:41:45, hora local, HA mostraba aspiración de salmuera y enjuague lento mientras el controlador indicaba **“pekel-spoel traag up-flow”**. Esto contrasta esa fase concreta. HA había indicado llenado de salmuera a las 19:35:34, unos seis minutos antes. Con consultas cada 60 segundos, esta observación no valida independientemente la duración configurada ni demuestra un error respecto a los siete minutos de la lectura anterior. Los intentos abortados anteriores se excluyen de la validación de secuencia y duraciones. La opción de regeneración de HA permaneció desactivada: no valida la orden de inicio del campo 34.

Después del ciclo, HA mostraba capacidad restante **3429 L**, frente a los **1267 L** reportados el 8 de octubre. Se registra una recuperación de capacidad tras regenerar, sin calibración independiente de la unidad. Se mantienen dureza 280 mg/L, resina `F0 00` / referencia 240 y referencia por ciclo 15. Suponiendo dureza expresada como CaCO₃, `3,429 m³ × 28 °f ≈ 96 °f·m³`, unos `4 °f·m³/L` para los 24 L nominales de resina. Es una comprobación de coherencia, no una comparación con la resina configurada ni una prueba de la escala 0,1. El usuario recuerda una etiqueta L junto al ajuste antiguo, pero no está seguro; la unidad y correspondencia exacta con el campo local siguen pendientes.

Se incorpora evidencia de funcionamiento y de una fase, sin cambiar Alpha, códecs, permisos ni unidades provisionales. Las comparaciones anteriores son puntos de calibración pendientes: no se piden más pruebas, capturas ni diagnósticos a este contribuyente. La incidencia original de conexión/alta puede cerrarse independientemente de estas validaciones.

## Ajustes experimentales opcionales

En la entrada operativa del modelo 1, abre **Ajustes → Dispositivos y servicios → Runxin Local → Configurar**. Activa **los ajustes experimentales del modelo 1** y guarda. La recarga añade controles adicionales para límite de tiempo de caudal (6), hora de regeneración (10), sal añadida (43) y dureza (47). **El campo 4 está verificado: escrituras manuales del reloj y restauración mediante sincronización manual. Los campos 6/10/43/47 y la regeneración (34) siguen pendientes.** No hace falta repetir la prueba del reloj ya completada.

Para una prueba nueva, anota una lectura inicial nueva, cambia un solo ajuste una cantidad pequeña dentro del rango, comprueba la lectura posterior y pantalla/app si es visible, restaura el valor original y confírmalo. Aporta campo, valor inicial, solicitado, leído, unidad/pantalla y restauración. No repitas una orden con resultado ambiguo: la integración comprueba el estado sin reenviarla a ciegas.

Una **segunda opción** permite iniciar una regeneración prevista y requiere también el modo de ajustes. El botón comprueba servicio y vacaciones desactivadas con una lectura nueva, envía campo 34 = 1 una sola vez y comprueba la fase. El avance directo de fases sigue bloqueado, también en los servicios administrativos.

El **reloj automático**, el **campo 7**, vacaciones y escrituras de resina/capacidad siguen bloqueados. El dispositivo devolvió unidad 1; el control del umbral de caudal está calibrado para unidad 2. Las lecturas de resina y capacidad siguen siendo provisionales.

Desactivar los ajustes experimentales elimina solo los controles adicionales y desactiva también la prueba de regeneración. El reloj y la sincronización manuales siguen disponibles. Se revoca y sustituye la sesión anterior; se conservan sensores de referencia, identificadores, bytes y ausencia de estadísticas provisionales, también tras actualizar o reiniciar. Los diagnósticos separan evidencia del modelo y permisos efectivos. Exportarlos no inicia lecturas ni escrituras. G6 y modelos 12/14 mantienen su política.
