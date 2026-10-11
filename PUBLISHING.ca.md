[English](PUBLISHING.md) | [Español](PUBLISHING.es.md) | [Català](PUBLISHING.ca.md)

La **2.9.x** utilitza una etiqueta de release estable. Alpha és metadada de suport per model (1/12/14), no un requisit de prerelease de la integració. Una versió normal actualitza el canal estable.

# Publicar Runxin Local a GitHub i HACS

L'arbre de codi està preparat per al repositori públic `Danirv/runxin-local` i la seva distribució mitjançant HACS.

## 1. Metadades del repositori

En un clon/plantilla nou, configura el propietari una sola vegada:

```bash
python scripts/configure_repository.py Danirv --repo runxin-local
```

Després verifica:

```bash
python scripts/publication_check.py
python scripts/audit.py
python scripts/field_surface_audit.py
python -m pytest -q
python -m compileall -q custom_components/ypsilon_local scripts tests
```

## 2. Requisits del repositori

Mantén Issues habilitat i temes útils com `home-assistant`, `hacs`, `custom-component`, `water-softener`, `runxin`, `broadlink` i `ypsilon`.

El repositori inclou validació HACS, hassfest, auditoria offline de protocol/arquitectura i workflow automatitzat de releases. No ignoris errors de validació abans de publicar ni mentre hi hagi una sol·licitud d'inclusió a HACS oberta.

## 3. Publicar una GitHub Release des de la web

1. Tria una versió semàntica **nova i no utilitzada**. No reutilitzis mai una versió que ja tingui una GitHub Release, encara que `main` contingui codi posterior.
2. Actualitza `manifest.json`, `CHANGELOG.md` i `info.md` amb la mateixa versió.
3. Fusiona aquests canvis de release a `main` només quan HACS, hassfest i l'auditoria offline estiguin en verd.
4. Obre GitHub **Actions** → **Publish GitHub release**.
5. Prem **Run workflow** i comprova que la branca sigui `main`.
6. Executa el workflow.

El workflow web llegeix la versió de `custom_components/ypsilon_local/manifest.json`, executa publication check, auditoria, field-surface audit, tests i compilació, rebutja una GitHub Release existent, crea o recupera el tag anotat `v<versió>`, fa checkout exactament d'aquell tag, torna a validar el codi etiquetat, construeix el ZIP i crea la GitHub Release.

Un tag pujat manualment activa el job de tags, que aplica la mateixa validació. Un tag creat pel mateix workflow amb `GITHUB_TOKEN` no necessita un segon workflow: el job web finalitza la release després de validar el tag.

### Prereleases i manteniment

Una versió amb `-` (per exemple `2.9.0-alpha.1`) es publica automàticament amb `--prerelease --latest=false`; es conserva la selecció de l'última estable. Verifica el flag i el ZIP després de publicar. El suport/evidència per model és independent de l'etiqueta de release: Alpha no desactiva controls per si sol.

Els canvis de manteniment pendents necessiten una **versió nova abans de publicar**. No reutilitzis un tag publicat per distribuir codi posterior de main. Executa la suite nativa completa amb `requirements-test-ha.txt` i `requirements-test-ha-baseline.txt` en entorns separats; la feina de release executa la suite offline lleugera.

### Alternativa amb Git

```bash
VERSION="$(python -c 'import json; print(json.load(open("custom_components/ypsilon_local/manifest.json"))["version"])')"
git tag -a "v${VERSION}" -m "Runxin Local ${VERSION}"
git push origin "v${VERSION}"
```

No creïs manualment una altra GitHub Release per al mateix tag.

## 4. Provar mitjançant HACS

Abans de sol·licitar inclusió per defecte, afegeix el repositori com a Integration personalitzada, instal·la/actualitza, reinicia Home Assistant i verifica el camí real contra maquinari.

## 5. Inclusió per defecte a HACS

El projecte té una sol·licitud oberta a `hacs/default#10717`. El manteniment normal i noves releases poden continuar mentre espera revisió. No obris sol·licituds duplicades ni comentis al PR de cua llevat d'informació crítica o petició del revisor.

## Disciplina de release

Per a cada release:

1. Confirma que la versió prevista **no** existeixi ja com a GitHub Release.
2. Actualitza conjuntament `manifest.json`, `CHANGELOG.md` i `info.md`.
3. Executa publication check, audit, field-surface audit, pytest i compileall.
4. Fusiona només amb HACS/hassfest/audit en verd.
5. Publica preferentment des d'Actions a `main`; alternativament puja exactament `v<versió del manifest>`.
6. Verifica el tag, l'asset resultant i els checks de `main`.
7. No moguis ni recreïs mai un tag d'una release ja publicada per incorporar codi posterior: publica una nova versió patch.

No pugis mai APK del fabricant, firmware, binaris/scripts propietaris, credencials, claus privades/d'aparellament ni captures sense sanejar.
