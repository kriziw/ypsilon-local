[English](hardware-verification.md) | [Español](hardware-verification.es.md) | [Català](hardware-verification.ca.md)

# Verificació d'escriptures sobre maquinari

Un camp només es marca `HARDWARE_WRITE_VERIFIED` quan la integració local ha provat tota la ruta d'escriptura i lectura posterior contra un controlador físic. Un ACK o un còdec autocoherent no són suficients.

La correcció de vacances de la 2.6.1 continua sent un exemple deliberat d'aquesta regla: el camp 49 és codificable segons l'app antiga, però el G6 provat va donar ACK a l'escriptura local directa sense canviar l'estat en lectures fresques. Per això Home Assistant només exposa l'estat de vacances com a lectura.

## Seqüència requerida

Per a un camp de configuració reversible:

1. **GET inicial** — llegir el valor actual localment.
2. **SET candidat** — enviar una única escriptura amb el còdec que es vol validar.
3. **GET independent** — tornar a consultar físicament el controlador.
4. **Validació física/semàntica** — confirmar que l'estat observat significa el que s'espera.
5. **Restauració** — tornar a escriure el valor inicial.
6. **GET de restauració** — verificar que l'estat original s'ha recuperat.

No s'ha d'utilitzar estat cachejat del coordinator com a evidència. Per a una acció mecànica també cal validar la fase/transició física esperada.

## Lliurament ambigu

Si el SET ja s'ha enviat però es perd la resposta o hi ha timeout, **no es reenvia cegament**. El controlador podria haver-lo executat. Primer s'ha de fer un GET nou i reconciliar l'estat físic.

## Nivells d'evidència

- còdec de l'app → `LEGACY_APP_CODEC`;
- valor observat al dispositiu → `DEVICE_STATE_OBSERVED`;
- canvi observat al cloud → `CLOUD_WRITE_OBSERVED`;
- SET local + lectura física independent completa → `HARDWARE_WRITE_VERIFIED`.

## Estat actual Ypsilon G6 / F79D

Verificats localment de punta a punta:

- camp 4 — rellotge / sincronització;
- camp 6 — límit de consum continu;
- **camp 7 — llindar de tancament per cabal, u16 big-endian**;
- camp 10 — hora de regeneració;
- camp 43 — quantitat de sal afegida;
- camp 47 — duresa de l'aigua d'entrada.

Pendents o deliberadament no verificats:

- **camp 34** — escriptures mecàniques/màquina d'estats més enllà del comportament específic provat;
- **camp 49** — el control local directe `1/0` de vacances està explícitament no verificat al G6 provat i no s'exposa com a control HA.

## Evidència del camp 7

El G6 físic resol l'ordre de bytes del camp 7 independentment de la interpretació de l'app antiga:

```text
bytes al fil: 03 E8
big-endian:    0x03E8 = 1000 -> 10,00 m³/h
little-endian: 0xE803 = 59395 -> 593,95 m³/h
```

L'app oficial mostrava 10,00 m³/h mentre Ypsilon 2.6.2, amb la regressió LE, mostrava 593,95 m³/h. La via d'escriptura aporta una segona prova: 2,00 m³/h són raw 200 (`0x00C8`) i s'han d'enviar com `00 C8`; la regressió LE enviava `C8 00`, rebia ACK però el read-back físic no canviava i el coordinator generava `Write ACKed but not confirmed`.

Versions anteriors del projecte amb BE ja havien completat correctament el SET/read-back físic del camp 7. Sumant aquella verificació a l'evidència actual independent, el camp 7 torna a estar `HARDWARE_WRITE_VERIFIED`. La discrepància amb el còdec antic es conserva documentada, però per al G6 provat preval el controlador real.

## Evidència del falliment del camp 49

La UI antiga modela l'entrada de vacances des de station 0, la progressió `0 -> 3 -> 7 -> 2 -> 8` i l'estat estable com camp 49 cert + station 8. Al G6 provat, però, un SET local directe del camp 49 va rebre ACK i lectures locals independents repetides van continuar retornant `vacationPattern=false` fins al timeout. Per tant aquest mètode concret no funciona al maquinari provat i Ypsilon no inventa una seqüència mecànica alternativa.

## Evidència d'aigua i sal

L'històric real confirma que `dailyWaterConsumption` augmenta durant el dia i es reinicia al canvi de dia, cosa que dona suport a `TOTAL_INCREASING` per al camp 37. Les captures de l'app oficial mostren que el camp 39 no és el mateix que les barres de totals setmanals històrics, de manera que els camps 39 i 41 no tenen `state_class`.

El camp 43 té SET/read-back local verificat i canvi observat per cloud. La seva semàntica és «sal afegida» en kg, no un sensor físic de nivell.

## Euro-Clear Midnight / model de controlador 12

**Suport experimental / Alpha, limitat al model 12 i provat inicialment amb Midnight 25.** Els controls continuen disponibles per validar-los i conserven el read-back estricte; aquest estat no certifica les ordres pendents. L'evidència del G6 no es transfereix automàticament al model 12. El catàleg compartit `FieldSpec` descriu l'evidència del G6 de referència; l'evidència per model és a `models.py` i als diagnòstics.

Maquinari: Euro-Clear Midnight 25 (capçal ECOPRO+) amb mòdul BroadLink BL3372 (devtype `0x520F`), que informa `deviceModel` 12. Provat el 2026-10-04 amb la vàlvula en servei i les vacances desactivades.

Una lectura completa dels camps 1–52 es descodifica de manera coherent amb el mapa F79D i la pantalla del controlador. Diferències: el camp 26 informa dècimes de litre (250 en una unitat de 25 L), i els camps 24 (valor 2) i 9 (valor 255) queden fora dels enums recuperats.

Verificat localment d'extrem a extrem (GET base → un SET → GET nou → restauració → GET nou, sense efectes secundaris en altres camps): camp 43 `saltAddition` 23 → 24 → 23, camp 10 `regeneratingTriggerTime` 00:00 → 00:01 → 00:00, camp 6 `continuousWaterTime` 0 → 120 → 0 i camp 4 `currentTime` (sincronització 16:31 → 16:32).

Encara sense verificació física al model 12: camp 7 (`flowRateOff`, llegeix `00 C8` = 2,00 m³/h en big-endian), camp 47 (`rawWaterHardness`) i la regeneració forçada del camp 34.

`FA 00` del camp 26 confirma la visualització actual de 25 L al Midnight 25; no determina el significat del segon byte ni el còdec de volums més grans. Es conserven U8 i l'escala 0,1, i `_raw_resinVolumeBytes` desa els dos bytes per investigar-los.

### Investigació dels enums i la duresa del model 12 (2026-10-05)

S'han consultat el [manual del fabricant Euro-Clear Midnight (2025)](https://euro-clear.eu/shop/wp-content/uploads/2025/11/2025_Midnight_gepkonyv_HU.pdf) i el [manual Runxin F105/F136](https://manufacturervalve.com/pdf/download-center_22.pdf). No estableixen una correspondència del camp 9 amb valor 255 ni del camp 24 amb valor 2 amb cap etiqueta. El model físic de vàlvula o un menú no equival automàticament al codi del controlador BroadLink ni a un enum del protocol. Es mostren els codis decimals `255` i `2` i es conserva `raw_code` fins que hi hagi evidència específica. Les dades absents continuen sent `unknown`; les etiquetes conegudes es conserven.

[WaterCare 0.6.0](https://github.com/kriziw/Euroclear-broadlink/tree/2b5b5076e6131d96d98b2263e1f7ee47ce388db7) reutilitza el nostre mapa i també mostra aquests codis crus. És evidència d'interoperabilitat, no una confirmació independent del significat. El contribuent indica que WaterDevice no es connecta a aquesta unitat; comparar amb la pantalla física i amb una lectura HA nova és útil sense exigir una app del fabricant que no funciona.

El manual Midnight, pàgina impresa 16, indica multiplicar la duresa alemanya mesurada (nk°) per 10 (15 → 150 mg/L); en un altre apartat (pàgina 7) expressa la duresa de l’aigua com a CaO mg/L. Aquesta convenció ajuda a comparar lectures del model 12. Es conserven el valor informat, la unitat HA mg/L i el rang d'escriptura; no s'aplica cap conversió silenciosa ni es generalitza aquesta convenció al G6.

### Validacions pendents

- Camps 7 i 47: GET inicial → un SET adequat → GET nou → comparació amb pantalla/app → restauració → GET nou. Incloure els dos bytes, el valor demanat i qualsevol error de confirmació.
- Camp 26: informar dels dos bytes i del volum de resina mostrat a pantalla/app. No cal una altra unitat; els volums més grans queden pendents fins obtenir evidència.
- Durant una regeneració prevista, comprovar que el botó HA inicia el cicle físic i que les fases llegides concorden. L'avanç de fase és una acció pendent separada; no cal saltar fases per completar aquestes proves.
- Confirmar 25 L a HA, els codis decimals `2`/`255` amb `raw_code` per als enums sense correspondència i possibles errors recurrents durant l'ús normal.

Els resultats parcials són útils. Incloure model, firmware, data, valors inicials/restaurats i diagnòstics anonimitzats; ometre MAC, IP i credencials. Aquestes proves no es consideren completades fins que un contribuent n'informi.

## Camp 52

El camp 52 queda intencionadament fora del bloc normal 1..51. La capa Ypsilon el consulta i cacheja per separat perquè és un interval de servei que canvia lentament.

## Regla de generalització

L'evidència d'un controlador o firmware no s'ha de generalitzar automàticament a tots els dispositius Runxin. Abans d'ampliar suport a un altre transport, rebrand o firmware, cal verificar independentment còdec i comportament físic.

Consulta també [`waterdevice-audit.ca.md`](waterdevice-audit.ca.md).

## Controlador sense marca model 1 / F150: rellotge confirmat

La [resposta del 10-10-2026 a la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) informa valor inicial 11:23, escriptures manuals des de HA a 11:24 i 11:26 i restauració amb sincronització manual. Pantalla i Water Device coincideixen a cada pas. Es registra **camp 4, rellotge/sincronització manuals verificats** en aquest equip (firmware BL3372 62016); els camps 6/10/34/43/47 continuen pendents. La 2.9.3 habilita només els controls manuals verificats del camp 4 per defecte. La resta conserva les opcions explícites; es mantenen els sensors de referència i la correcció automàtica bloquejada.

El codi d’idioma 7 és neerlandès a la pantalla. El G6 model 9 del projecte retorna codi 3 amb menús en castellà; consulta [les correspondències limitades per model](f79d-settings.ca.md). No és una validació de tot l’enum ni de l’idioma de l’app/compte.

Resina crua 240 i referència per cicle 15 són lectures diferents sense conversió confirmada. L’usuari va modificar 24 → 15 sota l’etiqueta Water treatment capacity de l’app antiga; falten unitat i correspondència exacta amb el camp local. Els 24 L nominals fan plausible una escala 0,1 però no confirmen el paràmetre configurat. No cal repetir rellotge/diagnòstics ni aplicar el còdec del model 14. [Guia del model 1](model-1-alpha.ca.md).

### Funcionament del model 1 i observació d’una fase amb la 2.9.3

La [resposta posterior de la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirma lectures periòdiques normals, recuperació després dels reinicis de HA i coincidència amb la pantalla en aspiració de salmorra / esbandida lenta ascendent. No valida totes les fases ni les durades configurades: s’exclouen els intents avortats i l’observació aproximada de l’ompliment es va fer amb lectures cada 60 segons. L’opció de regeneració de HA estava desactivada; l’escriptura del camp 34 continua pendent.

HA va mostrar capacitat restant 3429 L després del cicle, mantenint resina crua 240 i referència per cicle 15. Són lectures reportades i una comprovació de coherència, no una confirmació independent de l’escala de resina o les unitats de capacitat. L’etiqueta L de l’ajust antic es recorda amb incertesa. Alpha i escriptures pendents es mantenen; no es demanen més proves ni informes al contribuent. La incidència original de connexió/alta es pot tancar independentment. [Registre detallat](model-1-alpha.ca.md#funcionament-reportat-després-de-regenerar-amb-la-293).

## Euro-Clear Midnight / controlador model 14 (F136)

**Beta a la 2.9.2**, contrastada al Euro-Clear Midnight 25 Plug&Play / F136 / ECOPRO+, BL3372 `0x520F`, firmware **62016**. La [issue #22](https://github.com/Danirv/runxin-local/issues/22) confirma funcionament amb 2.9.1 després d’actualitzar/reiniciar, sense modificar models localment. Les lectures **4/6/7/10/43/47** coincideixen amb l’app (camp 7: 3,5 m³/h; camp 47: 260 mg/L). Les escriptures **4/6/10/43** estan verificades per l’usuari; **les escriptures 7/47 i les accions mecàniques de 34 continuen pendents**.

El camp 26 `[44, 1]` coincideix als diagnòstics i a l’informe independent de lectura. La [foto del controlador](https://github.com/Danirv/runxin-local/issues/22#issuecomment-6084624961) mostra **30,0 L** configurats. U16 little-endian dona `0x012C = 300`, amb escala 0,1 per obtenir 30,0 L. La 2.9.2 aplica l’excepció només al model 14 i marca `resin_volume_scale_confirmed=true`; G6/model 12 mantenen els seus còdecs. Els 25 L nominals són diferents del paràmetre configurat; no es canvia cap ajust. És una comparació de bytes reportats i pantalla, no una trama completa capturada ni una nova prova d’escriptura del mantenidor. No cal més comparació de resina ni repetir l’informe. [Guia del model 14](model-14-alpha.ca.md).
