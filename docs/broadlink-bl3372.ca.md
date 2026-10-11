[English](broadlink-bl3372.md) | [Español](broadlink-bl3372.es.md) | [Català](broadlink-bl3372.ca.md)

# Transport BroadLink BL3372

`transport/broadlink_bl3372.py` és el transport concret utilitzat actualment per
la integració Home Assistant i està separat deliberadament del codec F79D.

## Combinació provada

- devtype BroadLink: `0x520F`
- mòdul: BL3372
- controlador: Runxin F79D
- comanda BroadLink per a dades de producte: `0x6A`
- dependència Python: `python-broadlink==1.0.6`

Provar un altre devtype en recerca no significa que aquella combinació quedi
suportada per Ypsilon.

## Ruta de transacció

```text
trama Runxin crua
 -> prefix uint16-le de longitud (TFB)
 -> send_packet(0x6A, ...)
 -> validar resposta externa BroadLink
 -> desxifrar cos
 -> treure longitud/padding TFB
 -> trama Runxin crua
```

El transport mai descodifica camps F79D.

## Sessió i reintents de lectura

Es reutilitza una sessió autenticada i les transaccions se serialitzen. En
lectures idempotents:

- resposta externa `-1` / `-7` després d'autenticar: es permet una nova autenticació;
- `-5`: és empíricament transitori al maquinari provat i admet reintents breus,
  acotats i amb jitter;
- els pressupostos de reautenticació i `-5` són independents.

La causa interna exacta de `-5` **no està demostrada**.

## Escriptures: sense reintent cec

Les escriptures usen `transact_write()` i s'envien **com a màxim una vegada**. Si
es perd la resposta, caduca la sessió o apareix un error després de l'enviament,
el resultat és ambigu: l'F79D ja podria haver executat el SET.

Per això no es reenvia automàticament. El coordinador fa un GET local nou i
reconcilia l'estat físic. Si coincideix, l'operació s'accepta encara que s'hagi
perdut l'ACK; si no, acaba com a no confirmada. És especialment important en
accions mecàniques com forçar una regeneració.

## Diagnòstics

S'exposen comptadors de reintents transitoris de lectura, reautenticacions i
versió de firmware BroadLink quan es pot llegir.

També es conserva l'última etapa del transport, el tipus de dispositiu, el
bloqueig anunciat i el tipus/codi de l'última transacció fallida. El bit anunciat
no impedeix intentar l'autenticació. El rebuig del handshake inicial es distingeix
dels errors externs posteriors i no es reintenta automàticament. Els nous logs
ometen identificadors, claus, paquets i text de les excepcions. Consulta la
[guia de connexió](troubleshooting.ca.md) per obtenir logs o l'informe independent.

## Substituir BroadLink

Un altre transport només ha d'acceptar i retornar trames Runxin crues. TFB,
`0x6A`, xifrat BroadLink i errors externs no formen part del contracte genèric.

Consulta [`adding-a-transport.ca.md`](adding-a-transport.ca.md).
