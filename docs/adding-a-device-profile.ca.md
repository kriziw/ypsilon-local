[English](adding-a-device-profile.md) | [Español](adding-a-device-profile.es.md) | [Català](adding-a-device-profile.ca.md)

# Afegir un altre perfil de dispositiu Runxin

No copiïs la taula F79D canviant-li el nom. Tracta un altre controlador com a no verificat fins que les lectures demostrin què és compartit. Un controlador compatible pot reutilitzar el perfil de protocol amb política pròpia; compartir trames no demostra semàntica física idèntica.

## Política de controlador i perfil de protocol

Si el mapa compartit està demostrat, reutilitza el còdec i afegeix una entrada `ControllerModel` amb evidència, permisos explícits, incertesa de conversions i entitats aplicables. `allowed_write_fields` és buit per defecte. Una Alpha de lectura pot mostrar referències provisionals, però ha de bloquejar rellotge, serveis i escriptures directes i desactivar les estadístiques provisionals.

Les diferències demostrades necessiten overrides i fixtures per model, sense modificar els valors per defecte del G6/Midnight. Un mapa diferent requereix un perfil i selector explícits; `protocol_profile` encara no és una fàbrica genèrica. Cal provar absències, enums desconeguts, intents de saltar permisos, reinicis i identitats existents.

Consulta la [política de suport](model-support.md) i el [model 1](model-1-alpha.ca.md).


## Flux de treball recomanat

1. Identifica per separat el controlador/model i el transport.
2. Captura primer trànsit només de lectura.
3. Confirma si el format de trama en brut coincideix amb `runxin/framing.py`.
4. Determina el camp de model/identitat i un conjunt mínim i segur de lectura.
5. Crea un catàleg declaratiu de camps amb codecs i evidència explícits.
6. Afegeix proves offline amb trames de referència i regressió.
7. Només llavors investiga escriptures, camp a camp, amb lectura física posterior.
8. Mantén els controls de Home Assistant més restringits que la capacitat teòrica d'escriptura del protocol fins a entendre rangs i conseqüències.

## Reutilitzar el framing compartit

Si el dispositiu nou usa la mateixa envolupant `5A 5C` / `DF FD` i els mateixos opcodes de petició/resposta, reutilitza `runxin/framing.py`. Si no, afegeix una implementació de framing separada en lloc de relaxar la validació per acceptar formats de paquet no relacionats.

## Catàleg de camps

Usa `FieldSpec` / `FieldCodec` de `runxin/fields.py` com a patró. Conserva:

- id de camp;
- nom semàntic estable;
- codec de lectura;
- codec d'escriptura conegut, si n'hi ha;
- notes d'unitat/escalat;
- procedència/evidència.

No amaguis la incertesa. `inferred` és preferible a presentar una hipòtesi com un fet de protocol verificat.

## El suport a Home Assistant és una decisió separada

Un perfil reutilitzable pot existir al repositori abans que la integració Runxin Local el suporti. Afegir-lo al descobriment automàtic/config flow requereix treball addicional: nom del model, identitat del dispositiu, aplicabilitat d'entitats, política d'escriptures segures, traduccions, diagnòstics i proves amb maquinari real.

Aquesta separació permet que la feina d'enginyeria inversa sigui útil sense fingir que un model nou està preparat per a producció.

## Higiene de l'evidència

Aporta captures sanejades, taules de camps descodificades i fixtures de prova escrits de forma independent. No pugis APK del fabricant, firmware, volcats de codi descompilat, claus privades, credencials ni secrets.
