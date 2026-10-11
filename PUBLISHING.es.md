[English](PUBLISHING.md) | [Español](PUBLISHING.es.md) | [Català](PUBLISHING.ca.md)

**2.9.x** utiliza una etiqueta de release estable. Alpha es metadato de soporte por modelo (1/12/14), no un requisito de prerelease de la integración. Una versión normal actualiza el canal estable.

# Publicar Runxin Local en GitHub y HACS

El árbol de código está preparado para el repositorio público `Danirv/runxin-local` y su distribución mediante HACS.

## 1. Metadatos del repositorio

En un clon/plantilla nuevo, configura el propietario una sola vez:

```bash
python scripts/configure_repository.py Danirv --repo runxin-local
```

Después verifica:

```bash
python scripts/publication_check.py
python scripts/audit.py
python scripts/field_surface_audit.py
python -m pytest -q
python -m compileall -q custom_components/ypsilon_local scripts tests
```

## 2. Requisitos del repositorio

Mantén Issues habilitado y temas útiles como `home-assistant`, `hacs`, `custom-component`, `water-softener`, `runxin`, `broadlink` y `ypsilon`.

El repositorio incluye validación HACS, hassfest, auditoría offline de protocolo/arquitectura y workflow automatizado de releases. No ignores fallos de validación antes de publicar ni mientras haya una solicitud de inclusión en HACS abierta.

## 3. Publicar una GitHub Release desde la web

1. Elige una versión semántica **nueva y no utilizada**. Nunca reutilices una versión que ya tenga una GitHub Release, aunque `main` contenga código posterior.
2. Actualiza `manifest.json`, `CHANGELOG.md` e `info.md` con la misma versión.
3. Fusiona esos cambios de release en `main` solo cuando HACS, hassfest y la auditoría offline estén en verde.
4. Abre GitHub **Actions** → **Publish GitHub release**.
5. Pulsa **Run workflow** y comprueba que la rama sea `main`.
6. Ejecuta el workflow.

El workflow web lee la versión de `custom_components/ypsilon_local/manifest.json`, ejecuta publication check, auditoría, field-surface audit, tests y compilación, rechaza una GitHub Release existente, crea o recupera el tag anotado `v<versión>`, hace checkout exactamente de ese tag, vuelve a validar el código etiquetado, construye el ZIP y crea la GitHub Release.

Un tag subido manualmente activa el job de tags, que aplica la misma validación. Un tag creado por el propio workflow con `GITHUB_TOKEN` no necesita un segundo workflow: el job web finaliza la release después de validar el tag.

### Prereleases y mantenimiento

Una versión con `-` (por ejemplo `2.9.0-alpha.1`) se publica automáticamente con `--prerelease --latest=false`; se conserva la selección de la última estable. Verifica el flag y el ZIP después de publicar. El soporte/evidencia por modelo es independiente de la etiqueta de release: Alpha no desactiva controles por sí solo.

Los cambios de mantenimiento pendientes necesitan una **versión nueva antes de publicar**. No reutilices un tag publicado para distribuir código posterior de main. Ejecuta la suite nativa completa con `requirements-test-ha.txt` y `requirements-test-ha-baseline.txt` en entornos separados; el trabajo de release ejecuta la suite offline ligera.

### Alternativa con Git

```bash
VERSION="$(python -c 'import json; print(json.load(open("custom_components/ypsilon_local/manifest.json"))["version"])')"
git tag -a "v${VERSION}" -m "Runxin Local ${VERSION}"
git push origin "v${VERSION}"
```

No crees manualmente otra GitHub Release para el mismo tag.

## 4. Probar mediante HACS

Antes de solicitar inclusión por defecto, añade el repositorio como Integration personalizada, instala/actualiza, reinicia Home Assistant y verifica el camino real contra hardware.

## 5. Inclusión por defecto en HACS

El proyecto tiene una solicitud abierta en `hacs/default#10717`. El mantenimiento normal y nuevas releases pueden continuar mientras espera revisión. No abras solicitudes duplicadas ni comentes en el PR de cola salvo información crítica o petición del revisor.

## Disciplina de release

Para cada release:

1. Confirma que la versión prevista **no** exista ya como GitHub Release.
2. Actualiza conjuntamente `manifest.json`, `CHANGELOG.md` e `info.md`.
3. Ejecuta publication check, audit, field-surface audit, pytest y compileall.
4. Fusiona solo con HACS/hassfest/audit en verde.
5. Publica preferentemente desde Actions en `main`; alternativamente sube exactamente `v<versión del manifest>`.
6. Verifica el tag, el asset resultante y los checks de `main`.
7. No muevas ni recrees nunca un tag de una release ya publicada para incorporar código posterior: publica una nueva versión patch.

Nunca subas APK del fabricante, firmware, binarios/scripts propietarios, credenciales, claves privadas/de emparejamiento ni capturas sin sanear.
