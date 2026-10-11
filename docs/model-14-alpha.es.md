# Modelo 14 / Runxin F136: soporte Midnight Beta

[English](model-14-alpha.md) | [Català](model-14-alpha.ca.md) | [Español](model-14-alpha.es.md)

Runxin Local **2.9.2** pasa el **modelo 14 / F136 a Beta** y corrige la lectura de resina. Hardware contrastado en la [issue #22](https://github.com/Danirv/runxin-local/issues/22): Euro-Clear Midnight 25 Plug&Play / ECOPRO+, BroadLink BL3372 (`0x520F`), firmware **62016**. La release es estable; los modelos 1 y 12 siguen Alpha.

## Evidencia confirmada

El usuario confirma que **2.9.1 funciona sin modificaciones locales**, después de actualizar y reiniciar HA. Los diagnósticos y el informe independiente de lectura coinciden en los bytes de resina. Las lecturas **4/6/7/10/43/47** coinciden con la app; el campo 7 muestra **3,5 m³/h** y el 47 **260 mg/L**.

Las escrituras **4/6/10/43** están verificadas por el usuario. Las **escrituras de 7/47 y las acciones mecánicas de 34 siguen pendientes**: comparar lecturas no valida escrituras. Beta no certifica esas acciones ni todas las variantes F136.

## Resina

La [foto y confirmación del controlador](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) muestran **H1-1 / Set Resin Volume = 30,0 L**. `[44, 1]` son bytes decimales: `0x012C = 300` en U16 little-endian; dividido entre 10 da **30,0 L**. La 2.9.1 descartaba el segundo byte y mostraba 4,4 L. La **2.9.2 corrige el modelo 14** y marca `resin_volume_scale_confirmed=true` en diagnósticos. Se conservan los bytes originales en el sensor y los diagnósticos.

Es el **valor configurado**, no una medición física de la resina. Los 25 L nominales del fabricante son un dato distinto: mostramos los 30 L configurados sin cambiarlos. No se necesitan más informes ni modificar ajustes para resolver este punto.

La excepción U16 solo se aplica al modelo 14. El G6/modelo 9 conserva U8 en litros; el modelo 12 conserva U8 × 0,1, porque `FA 00` no determina independientemente el significado del segundo byte. Los enums desconocidos siguen visibles como códigos decimales.

## Instalación y controles

Instala **2.9.2 o posterior** para corregir la resina y reinicia HA. Las entradas operativas se actualizan conservando dominio `ypsilon_local`, identidades MAC, unique IDs y controles: no hay que editar el registro ni volver a añadir el dispositivo. Las entradas solo de diagnóstico siguen siendo de diagnóstico.

Los controles Midnight mantienen codificaciones, rangos, comprobaciones de estado y lectura posterior estricta. Los controles pendientes siguen disponibles; vacaciones es solo lectura. No se añaden consultas ni escrituras. Las lecturas parciales del campo 26 reutilizan la identidad validada.

## Validación pendiente

No es necesario repetir pruebas completadas ni enviar otro diagnóstico ahora. Cuando sea conveniente, una prueba adecuada de escritura de 7 o 47 puede hacer: lectura inicial → cambio desde HA → lectura nueva y comparación con app/controlador → restauración → lectura nueva. No hay que superar el umbral de caudal ni provocar regeneración para validar un ajuste. La prueba mecánica del campo 34 es independiente y no se solicita solo para completar el informe. [Verificación física](hardware-verification.es.md).
