[English](CONTRIBUTING.md) | [Español](CONTRIBUTING.es.md) | [Català](CONTRIBUTING.ca.md)

# Contribuir

Les contribucions són benvingudes. El projecte prioritza control local fiable, reconciliació explícita de l'estat, escriptures mecàniques conservadores i coneixement d'interoperabilitat reutilitzable.

## Abans d'obrir un pull request

1. Instal·la `requirements-test-offline.txt` en un entorn Python aïllat i executa `python -m pytest -q`, `python scripts/audit.py` i `python scripts/field_surface_audit.py`.
2. Executa `python scripts/publication_check.py` en un clon públic configurat.
3. Executa `python -m compileall -q custom_components/ypsilon_local scripts tests`.
4. Mantén els textos visibles per a l'usuari als fitxers de traducció (`en`, `es`, `ca`).
5. Prefereix canvis petits i revisables i conserva els unique ids d'entitats/config entries llevat que hi hagi una migració.
6. En escriptures, diferencia transport de l'ordre, ACK de protocol i estat físic confirmat.

## Límits d'arquitectura

La CI principal manté les proves de protocol lleugeres. Per provar config flow,
entitats i controls amb classes reals de Home Assistant, usa Python 3.14,
instal·la `requirements-test-ha.txt` i executa
`python -m pytest -q`.
Aquestes proves simulen l'E/S del dispositiu i no estableixen evidència física.

Llegeix [`docs/architecture.ca.md`](docs/architecture.ca.md) abans de treballar amb el protocol.

- `runxin/` ha de continuar independent de Home Assistant i BroadLink.
- Els transports porten trames Runxin en brut i no han de descodificar camps F79D.
- Paquets, xifrat i sessió pertanyen a la implementació del transport.
- IDs de camp, codecs i evidència pertanyen al perfil de dispositiu.
- Home Assistant decideix quines escriptures conegudes són segures d'exposar.
- `protocol.py` és una façana de compatibilitat, no el lloc per a lògica nova.

La feina nativa executa tota la suite amb HA 2026.9.4; una altra usa `requirements-test-ha-baseline.txt` amb HA 2026.9.3. Són versions provades amb E/S simulada, no una versió mínima declarada.

Les revisions del codi de les accions estan fixades, però HACS/hassfest encara utilitzen etiquetes de contenidors que poden canviar. Això no fixa tota la cadena d'eines. Les comprovacions d'imports són estàtiques; no aïllen el codi durant l'execució.

Per a un model compatible nou, reutilitza el mapa compartit, documenta la incertesa d'unitats/aplicabilitat i comença amb permisos d'escriptura buits. Les proves Alpha han de cobrir els bloquejos de rellotge, serveis i adaptador, i conservar identitats i conversions del G6/model 12. Una família de protocol diferent necessita evidència i perfil propis. Consulta la [matriu de suport](docs/model-support.md) i la [guia de verificació física](docs/hardware-verification.ca.md).

## Recerca del protocol i dades de prova

No publiquis APK del fabricant, firmware, scripts/binaris propietaris, credencials, claus privades o d'aparellament, tokens de compte ni captures sense sanejar amb identificadors d'usuari/dispositiu.

Els fixtures petits i sanejats necessaris per provar codi escrit de manera independent són acceptables si no contenen secrets ni parts substancials de codi/contingut del fabricant.

Quan documentis un fet d'enginyeria inversa, diferencia evidència recuperada de l'app antiga, comportament observat en un dispositiu real, una escriptura físicament verificada i una inferència. És preferible marcar alguna cosa com `inferred` que presentar-la com una certesa falsa.

## Nous transports

Consulta [`docs/adding-a-transport.ca.md`](docs/adding-a-transport.ca.md). Un transport ha d'implementar el contracte `transact(frame: bytes) -> bytes` i retirar únicament la seva pròpia envolupant abans de retornar la resposta.

## Nous dispositius Runxin

Consulta [`docs/adding-a-device-profile.ca.md`](docs/adding-a-device-profile.ca.md). Inclou marca/model, controlador/vàlvula, identitat del transport/mòdul si es coneix i quins camps/ordres s'han verificat realment.

## Possible llibreria independent

La capa pura de protocol està preparada per poder-se extreure més endavant a una llibreria pública de PyPI si apareixen diversos consumidors reals. Fins aleshores, no introdueixis dependències runtime entre integracions HACS important un `custom_components.ypsilon_local` instal·lat.

## Llicència

En contribuir acceptes que la teva contribució es publica sota la llicència Apache 2.0 del repositori.
