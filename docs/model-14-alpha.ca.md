# Model 14 / Runxin F136: suport Midnight Beta

[English](model-14-alpha.md) | [Català](model-14-alpha.ca.md) | [Español](model-14-alpha.es.md)

Runxin Local **2.9.2** passa el **model 14 / F136 a Beta** i corregeix la lectura de resina. Maquinari contrastat a la [issue #22](https://github.com/Danirv/runxin-local/issues/22): Euro-Clear Midnight 25 Plug&Play / ECOPRO+, BroadLink BL3372 (`0x520F`), firmware **62016**. La release és estable; els models 1 i 12 continuen Alpha.

## Evidència confirmada

L’usuari confirma que **2.9.1 funciona sense modificacions locals**, després d’actualitzar i reiniciar HA. Els diagnòstics i l’informe independent de lectura coincideixen en els bytes de resina. Les lectures **4/6/7/10/43/47** coincideixen amb l’app; el camp 7 mostra **3,5 m³/h** i el 47 **260 mg/L**.

Les escriptures **4/6/10/43** estan verificades per l’usuari. Les **escriptures de 7/47 i les accions mecàniques de 34 continuen pendents**: comparar lectures no valida escriptures. Beta no certifica aquestes accions ni totes les variants F136.

## Resina

La [foto i confirmació del controlador](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) mostren **H1-1 / Set Resin Volume = 30,0 L**. `[44, 1]` són bytes decimals: `0x012C = 300` en U16 little-endian; dividit per 10 dona **30,0 L**. La 2.9.1 descartava el segon byte i mostrava 4,4 L. La **2.9.2 corregeix el model 14** i marca `resin_volume_scale_confirmed=true` als diagnòstics. Es conserven els bytes originals al sensor i als diagnòstics.

És el **valor configurat**, no una mesura física de la resina. Els 25 L nominals del fabricant són una dada diferent: mostrem els 30 L configurats sense canviar-los. No calen més informes ni canviar cap ajust per resoldre aquest punt.

L’excepció U16 només s’aplica al model 14. El G6/model 9 conserva U8 en litres; el model 12 conserva U8 × 0,1, perquè `FA 00` no determina independentment el significat del segon byte. Els enums desconeguts continuen visibles com a codis decimals.

## Instal·lació i controls

Instal·la **2.9.2 o posterior** per corregir la resina i reinicia HA. Les entrades operatives s’actualitzen conservant domini `ypsilon_local`, identitats MAC, unique IDs i controls: no cal editar el registre ni tornar a afegir el dispositiu. Les entrades de només diagnòstic continuen sent de diagnòstic.

Els controls Midnight mantenen codificacions, rangs, comprovacions d’estat i lectura posterior estricta. Els controls pendents segueixen disponibles; vacances és només de lectura. No s’afegeixen consultes ni escriptures. Les lectures parcials del camp 26 reutilitzen la identitat validada.

## Validació pendent

No cal repetir proves completades ni enviar un altre diagnòstic ara. Quan sigui convenient, una prova adequada d’escriptura de 7 o 47 pot fer: lectura inicial → canvi des de HA → lectura nova i comparació amb app/controlador → restauració → lectura nova. No cal superar el llindar de cabal ni provocar regeneració per validar un ajust. La prova mecànica del camp 34 és independent i no es demana només per completar l’informe. [Verificació física](hardware-verification.ca.md).
