# Semàntica dels ajustos F79D recuperats

Aquest document recull els ajustos recuperats de la pantalla avançada de l'antiga WaterDevice i deixa explícita la seva representació a Home Assistant. Complementa `f79d.ca.md`; que el còdec pugui codificar un camp no implica que sigui segur exposar-lo com a control d'escriptura.

## Camps enum

| Camp | Nom del protocol | Valors crus | Estats de Home Assistant | Política HA |
|---:|---|---|---|---|
| 2 | `language` | 0 xinès, 1 anglès, 2 espanyol, 3 francès, 4 rus, 5 italià, 6 alemany, 7 polonès | `chinese` … `polish` | enum de diagnòstic, deshabilitat per defecte |
| 3 | `deviceTimeScheme` | 0 12 hores, 1 24 hores | `12_hour`, `24_hour` | enum de diagnòstic, deshabilitat per defecte |
| 24 | `outRelayMode` | 0 `b-01`, 1 `b-02` | `b_01`, `b_02` | enum de diagnòstic, deshabilitat per defecte |
| 48 | `absorbSaltMode` | 0 aspiració inversa (`逆吸`), 1 aspiració directa (`顺吸`) | `reverse`, `forward` | enum de diagnòstic, deshabilitat per defecte |

Les claus d'estat estables de Home Assistant no utilitzen text traduït. El codi cru original es conserva a l'atribut `raw_code` de l'entitat.

## Evidència de l’idioma del controlador (2.9.3)

La fila anterior és la **taula DeviceLanguage de referència**, no un mapatge universal dels controladors locals. La [definició de l’API del fabricant](https://api.waterdevice.net/api/abp/api-definition?includeTypes=true) associa `DeviceProtocolDataDto.Language` amb `Devices.Protocols.DeviceLanguage`; l’idioma del compte/app utilitza altres enums (`Identity.LanguageType` / `LanguageVersion`). El frontend examinat vincula els selectors de dispositiu i de compte per separat. Una coincidència de codis no demostra que puguem substituir una taula per l’altra.

| Model | Codi del camp 2 | Referència | Idioma confirmat a la pantalla |
|---|---|---|---|
| 1, issue #17 | 7 | Polonès | Neerlandès |
| 9, Ypsilon G6 del projecte | 3 | Francès | Castellà |

La [resposta de la issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) confirma neerlandès. Els diagnòstics del G6 indiquen model 9/codi 3 i els menús físics són en castellà. `device_language_keys()` aplica només aquestes correspondències, amb opcions enum traduïdes i `raw_code` conservat. Els models 12/14 i els altres codis mantenen la referència. Una lectura absent continua unknown i un codi desconegut es mostra en decimal. No s’exposa escriptura d’idioma.

No s’ha demostrat la causa de la discrepància local/referència. El firmware BroadLink 62016 és el del mòdul Wi-Fi, no demostra que dues vàlvules comparteixin firmware ni taula d’idiomes.

El sensor d’idioma també informa `controller_model` i `interpretation` (`controller_display_confirmed` o `reference_device_language_enum`) per distingir etiquetes observades de les de referència.

## Camps numèrics recuperats de la mateixa UI

| Camp | Nom del protocol | Rang WaterDevice | Representació HA |
|---:|---|---:|---|
| 13 | `washingIncreaseNumber` | 0–20 | sensor de diagnòstic només lectura, deshabilitat per defecte |
| 14 | `backWashIntervalNumber` | 0–20 | sensor de diagnòstic només lectura, deshabilitat per defecte |
| 25 | `regenerationAlarmNumber` | 5–1200 | sensor de diagnòstic només lectura, habilitat per defecte |

WaterDevice etiqueta el camp 25 com el recompte de regeneracions usat per al recordatori. Al Ypsilon G6 provat el valor observat és 700. És útil com a llindar natiu per calcular el manteniment de la resina; **no** és el comptador actual de regeneracions.

## Ajustos d'escriptura existents: límits recuperats de la UI

WaterDevice limita el camp 6 (`continuousWaterTime`) a 0–120 minuts. Home Assistant replica aquest rang.

El camp 7 (`flowRateOff`) depèn de la unitat. La integració només habilita el `number` escrivible per a la família validada en metres cúbics (codi d'unitat 2), on WaterDevice limita la visualització a 10,00 m³/h. El protocol desa centèsimes, per tant el rang cru segur corresponent és 0–1000.

Els altres límits d'escriptura exposats es mantenen:

- camp 43 `saltAddition`: 0–100 kg;
- camp 47 `rawWaterHardness`: 50–1500 mg/L.

Aquests rangs de la UI són independents de la política d'evidència d'escriptura. Al Ypsilon G6 provat, el camp 7 està `HARDWARE_WRITE_VERIFIED` amb un valor de 16 bits **big-endian**. La lectura decisiva és `03 E8`, que correspon a raw 1000 / 10,00 m³/h; versions anteriors del projecte amb BE ja havien completat correctament l'escriptura i el read-back locals. La regressió LE de la 2.6.x produïa `593,95 m³/h` amb aquests mateixos bytes i fallava la confirmació estricta d'escriptura.

## Font de l'evidència

Els mapatges d’enums de referència i rangs de UI provenen de la configuració i dels mòduls recuperats del JavaScript de l'antiga WaterDevice. Per a l'ordre de bytes del camp 7 preval l'evidència física del G6 quan entra en conflicte amb la interpretació del còdec antic. `tests/test_recovered_settings_semantics.py`, `tests/test_f79d.py` i `scripts/audit.py` ho protegeixen contra regressions; les traduccions continuen completes en anglès, castellà i català.
