[English](troubleshooting.md) | [Español](troubleshooting.es.md) | [Català](troubleshooting.ca.md)

# Resolució de problemes de connexió

La descoberta, l'autenticació local i les lectures F79D són etapes diferents.
Que `broadlink.hello()` funcioni no demostra que el dispositiu accepti control local.

## Missatges i logs de configuració

Des de la 2.7.1, la configuració distingeix el rebuig d'autenticació (`invalid_auth`),
el rebuig amb bloqueig anunciat (`device_locked`) i altres fallades (`cannot_connect`).
El bit de bloqueig és una observació de la descoberta, no una causa demostrada.
Ypsilon continua intentant l'autenticació normal encara que aquest bit sigui cert.

Una configuració fallida emet un avís amb el resultat, l'etapa del transport, el
tipus d'excepció, el codi numèric, el tipus de dispositiu i el bloqueig anunciat.
No cal haver creat una entrada. Per obtenir més detall, activa la depuració al
menú de la integració o afegeix això a `configuration.yaml` i reinicia HA:

```yaml
logger:
  default: warning
  logs:
    custom_components.ypsilon_local: debug
```

Si ja tens una secció `logger:`, integra-hi aquesta opció sense duplicar-la.
Reprodueix un intent, recull les línies de Ypsilon i desactiva la depuració.
Els nous missatges de connexió ometen IP/MAC, noms, claus, paquets i el text cru
de les excepcions. Revisa els altres logs de HA abans de compartir-los.

Per a entrades configurades, descarrega els diagnòstics al menú de la integració
o del dispositiu. `connection.transport` conté l'última etapa, el tipus descobert,
el bloqueig anunciat i les metadades de l'última fallada. `last_error` es conserva
encara que després hi hagi una transacció correcta; `available` indica l'estat
actual del coordinador. Si la configuració inicial falla, encara no hi ha entrada
per descarregar: utilitza l'avís del log o el script independent.

## Informe independent

Des de l'arrel del repositori, en un entorn Python que ja tingui `python-broadlink==1.0.6`,
executa això substituint `DEVICE_IP` localment:

```bash
python scripts/debug_connection.py DEVICE_IP
```

El script fa una descoberta i una autenticació normal. Si s'autentica, també
intenta llegir el firmware. No envia ordres de configuració, bloqueig, provisió
ni regeneració i no consulta camps F79D. L'informe JSON inclou les versions de
Python/BroadLink, el timeout i els resultats per etapa; omet adreça, MAC, nom,
identificador de control, claus, paquets i text de les excepcions. El codi de
sortida 1 indica que l'autenticació no ha tingut èxit. La lectura de firmware
pot fallar separadament sense invalidar una autenticació correcta.

Utilitza, si pots, el mateix entorn Python i de xarxa de la prova original.
Un complement Terminal/SSH, HA Core i un altre PC poden tenir entorns diferents;
indica des d'on ho has executat. No substitueixis les dependències gestionades per HA.

## Si es rebutja l'autenticació

1. Indica si alguna vegada ha funcionat l'autenticació local, les versions de HA
   i la integració, el nom/versió de l'app i des d'on fas la prova.
2. Tanca l'app del fabricant i pausa altres clients locals; executa una prova nova.
3. Si l'app ofereix alguna opció de bloqueig/control local, indica'n l'estat.
   Consulta les instruccions del fabricant abans de modificar-la; no sabem si
   aquesta opció existeix en tots els firmwares de Water Device.

Un bloqueig anunciat amb rebuig justifica investigar aquesta hipòtesi. Un bit
fals no demostra que tot el control local estigui permès. La vinculació amb l'app
no prova, per si sola, que calgui una clau proporcionada pel núvol.

El bloqueig BroadLink està documentat a la [guia de Home Assistant](https://www.home-assistant.io/integrations/broadlink/#device-is-locked)
i a la [discussió upstream #377](https://github.com/mjg59/python-broadlink/issues/377).
Els exemples corresponen a altres dispositius; no són una reparació verificada
per al G6. No facis un reset de fàbrica, no eliminis la vinculació amb el núvol
ni enviïs un `set_lock(False)` suposat com a primer pas de diagnòstic.

Si persisteix el rebuig, es pot acordar una captura limitada a descoberta i
autenticació per comparar-la amb un G6 funcional. Acorda abans la recollida i
l'anonimització: no publiquis PCAPs complets, que poden contenir material de sessió
i identificadors. Aquesta investigació no necessita escriptures de configuració.

## Solució d'aparellament reportada a la issue #17

Un usuari amb Runxin/润新 iOS 2.0.0 va observar bloqueig anunciat i autenticació rebutjada. Tornar a fer l'aparellament complet amb Water Device 2.1.3 va substituir el vincle anterior: bloqueig false i autenticació correcta amb l'app tancada. No va reportar un restabliment de fàbrica del controlador ni canvis físics. Després només una de les apps veia/controlava el dispositiu.

És un cas documentat, no una regla per a totes les versions. Reaparellar pot substituir el vincle de l'app anterior; no és simplement afegir un segon client. No implementem claus cloud ni desbloqueig automàtic. No cal repetir el procediment en un dispositiu que ja funciona.

El controlador resultant retorna codi 1; autenticar no confirma identitat G6/model 9. [Issue #17](https://github.com/Danirv/runxin-local/issues/17) i [Alpha de lectura](model-1-alpha.ca.md).
