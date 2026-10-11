# Runxin Local per a Home Assistant

Integració local per a descalcificadors compatibles amb **Runxin F79D + BroadLink BL3372**, amb el Ypsilon G6 com a maquinari de referència i suport experimental per al Euro-Clear Midnight.

El **model 1 / F150** té una Alpha de lectures amb rellotge manual validat a la 2.9.3: sensors periòdics, sense escriptures automàtiques, amb proves manuals opcionals a la 2.9.1. Les lectures són provisionals, sense estadístiques de llarg termini; la resina i la quantitat per cicle no tenen unitat assumida. [Guia](model-1-alpha.ca.md).


A la **2.9.3**, el model 1 té opcions desactivades per defecte per provar els ajustos addicionals 6/10/43/47 i una segona opció per iniciar una regeneració prevista. Les escriptures manuals del rellotge i la restauració amb sincronització manual (camp 4) estan verificades; la resta continuen pendents. El rellotge automàtic, el camp 7 i l’avanç de fases continuen bloquejats. [Instruccions](model-1-alpha.ca.md).

## Correccions a la 2.9.3

Release estable amb etiquetes d’idioma confirmades a la pantalla: model 1/codi 7 → neerlandès i G6 model 9/codi 3 → castellà. Es conserva la taula de referència per als altres codis/models i el codi cru. El model 1 manté lectures Alpha, amb rellotge i sincronització manuals disponibles sense opció experimental; resina 240 i capacitat de tractament 15 continuen sent paràmetres diferents amb conversió pendent. [Evidència d’idioma](f79d-settings.ca.md).

## Compatibilitat a la 2.9.2

La **2.9.2 és una release estable**. Els models 1 / F150 i 12 / F105 continuen Alpha; el **model 14 / F136 passa a Beta**. La issue #22 confirma funcionament amb 2.9.1, lectures 4/6/7/10/43/47 coincidents amb l’app i resina configurada de **30,0 L** al controlador: `[44, 1]` són 300 en U16 little-endian, dividits per 10. La 2.9.2 corregeix els 4,4 L que es mostraven abans. Les escriptures 4/6/10/43 estan verificades; les de 7/47 i les accions mecàniques de 34 continuen pendents. Es mantenen el comportament G6/model 12 i les identitats existents. [Guia del model 14](model-14-alpha.ca.md).

## Autodiagnòstic i canvi de nom: 2.8.0

El projecte passa de Ypsilon a **Runxin Local**, amb repositori `Danirv/runxin-local`. Es conserven el domini, la carpeta, els serveis i els identificadors `ypsilon_local`; el canvi de nom no requereix tornar a afegir els dispositius ni modificar automatitzacions.

Si un controlador no està admès o falla l’alta, pots preparar un **informe de lectura des de Home Assistant**, sense instal·lar Python ni editar models. Confirma l’exploració, desa l’entrada de diagnòstic i descarrega els diagnòstics des del seu menú. L’entrada no activa entitats, controls, consultes periòdiques ni correccions del rellotge. Els informes parcials són útils i no es comparteixen automàticament. Cal eliminar aquesta entrada abans d’afegir el dispositiu normalment quan tingui suport.

La taula del fabricant associa 9 amb F79D, 12 amb F105 i 14 amb F136; només descriu els codis i no amplia els models admesos. Continua calguent contrastar les conversions amb l’app o la pantalla del controlador. Consulta la [guia d’informes de compatibilitat](compatibility-report.md).

- Descobriment DHCP i configuració manual per IP.
- Lectura local de cabal, consum diari, capacitat restant, fase de vàlvula, mode de regeneració, patró de treball i avisos.
- Escriptures amb lectura física posterior estricta: un ACK no es considera estat confirmat.
- Controls de duresa, quantitat de sal afegida, proteccions de cabal/temps, hora de regeneració, rellotge i regeneració forçada; l'evidència física es documenta per camp i model.
- Estat de vacances de només lectura; la 2.6.1 retira el switch de vacances perquè l'escriptura local directa del camp 49 no va quedar confirmada físicament al G6 provat.
- Diagnòstics per fases de rentat, dissolució de sal, pausa 1, errors, comunicació i manteniment.
- Traduccions CA/ES/EN i branding local amb icona quadrada i logo horitzontal independents.

El botó de regeneració només inicia el cicle després que una lectura nova confirmi servei i vacances desactivades, i rebutja peticions simultànies. Envia la mateixa ordre una sola vegada i comprova la fase resultant. Els enums sense correspondència mostren el codi decimal i conserven `raw_code`; les etiquetes conegudes es mantenen i les dades absents són `unknown`. El rellotge admet un minut d’avanç dins dels 60 segons posteriors a l’escriptura, també a mitjanit, només si una lectura prèvia nova demostra que el valor del minut següent ha canviat; l’hora de regeneració exigeix coincidència exacta.

## Compatibilitat nova a la 2.7.0

El **Euro-Clear Midnight (controlador model 12)** té suport **experimental / Alpha**, provat amb un Midnight 25 amb capçal ECOPRO+ i BroadLink BL3372 (`0x520F`). Les captures concorden amb la pantalla del controlador; les escriptures dels camps 4, 6, 10 i 43 estan verificades físicament. Els camps 7 i 47 i les accions mecàniques del camp 34 continuen disponibles per fer proves, però encara no estan verificats en aquest model.

El model 12 conserva el suport Alpha i els controls existents. Es conserven els controls i la verificació estricta del PR original; el suport del G6 no canvia. Els diagnòstics inclouen l'evidència per model i els dos bytes crus del camp 26. `FA 00` es continua mostrant com **25 L**; aquesta captura no determina el significat del segon byte ni el còdec de volums superiors a 25,5 L.

Consulta les [proves pendents del model 12](hardware-verification.ca.md#euro-clear-midnight--model-de-controlador-12).

## Canvi principal de la 2.6.3

El camp 7 (`flowRateOff`, llindar de tancament per cabal) torna a utilitzar **u16 big-endian** en lectura i escriptura i recupera `HARDWARE_WRITE_VERIFIED`.

La prova física és directa: el controlador retorna `03 E8` mentre l'app oficial mostra 10,00 m³/h. En BE és raw 1000; en LE es converteix erròniament en 59395 i Home Assistant mostrava 593,95 m³/h. Per escriure 2,00 m³/h, raw 200 s'ha d'enviar com `00 C8`. La regressió LE enviava `C8 00`, rebia ACK però el read-back físic no confirmava el canvi, i la verificació estricta de Ypsilon el rebutjava correctament.

Versions anteriors del projecte amb BE ja havien verificat físicament SET/read-back per aquest camp. La superfície HA es manté limitada a 0–10,00 m³/h en la família d'unitat 2 validada.

## Canvis principals de la 2.6.1

- Vacances: el camp 49 es continua llegint i el sensor `desactivat / preparant / actiu` es manté, però no s'exposa cap escriptura fins conèixer i verificar físicament l'acció local del firmware actual.
- Consum diari: es manté com a comptador `TOTAL_INCREASING` que creix durant el dia i es reinicia al canvi de dia.
- Camp 39: **Consum setmanal mitjà del controlador**. No és el total setmanal de les barres històriques de l'app oficial.
- Camp 41: **Capacitat de tractament per cicle**, no un comptador de consum.
- Camp 43: **Quantitat de sal afegida**, un valor de registre/configuració en kg; no és nivell de sal restant.
- Branding amb icona quadrada, logo horitzontal i variants 2x/dark.

## Estadístiques antigues de Home Assistant

Versions anteriors van crear estadístiques de llarg termini per al consum mitjà setmanal i la capacitat per cicle quan encara declaraven `state_class`. Després d'actualitzar, Home Assistant pot oferir eliminar aquelles estadístiques obsoletes. És correcte eliminar-les: això no elimina l'entitat ni l'històric normal del Recorder.

## Instal·lació

Amb HACS, afegeix `https://github.com/Danirv/runxin-local` com a repositori personalitzat de tipus **Integration** fins que quedi incorporat al catàleg per defecte. Manualment, copia `custom_components/ypsilon_local` a `/config/custom_components/ypsilon_local`.

## Consum d'aigua

Per a consum acumulat utilitza **Consum diari**. **Cabal** és una mostra instantània i pot no veure consums molt curts entre dos polls. Per obtenir un total real de la setmana a Home Assistant, deriva'l del comptador diari/estadístiques; no utilitzis el camp 39 com si fos el total de la setmana actual.

## Problemes de connexió

Consulta la [guia de resolució de problemes](troubleshooting.ca.md) per distingir descoberta, autenticació rebutjada i lectures F79D. Inclou logs de depuració i un script que genera un informe sense identificadors ni claus, encara que no puguis completar la configuració a HA.

## Seguretat

La integració pot canviar paràmetres i iniciar moviments de vàlvula. No és un controlador de seguretat certificat ni ha de ser l'única protecció contra fuites o inundacions. Conèixer el còdec no equival a verificar l'acció física. En la compatibilitat Alpha del model 12, els controls pendents es mantenen disponibles amb aquesta limitació documentada.

Consulta el [README principal](../README.md), [`waterdevice-audit.ca.md`](waterdevice-audit.ca.md), [`f79d.ca.md`](f79d.ca.md), [`hardware-verification.ca.md`](hardware-verification.ca.md), [SECURITY](../SECURITY.md) i [LEGAL](../LEGAL.md).

Consulta l’[índex de documentació](index.md), la [matriu de suport](model-support.md).
