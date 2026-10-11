# Controlador model 1 / F150: lectures Alpha i rellotge manual validat

[English](model-1-alpha.md) | [Català](model-1-alpha.ca.md) | [Español](model-1-alpha.es.md)

La versió **2.9.0** admet el codi de controlador **1** amb sensors de lectura periòdica. El fabricant anomena aquest codi **F150**, però no tenim confirmat el producte comercial ni la vàlvula de la issue #17. No és suport general per a qualsevol equip F150.

La release de la integració és estable; Alpha descriu només el suport d’aquest model.

## Instal·lació i comparació

1. Instal·la la versió 2.9.3 o posterior amb HACS, o descarrega el ZIP de la release i copia només `custom_components/ypsilon_local` a `/config/custom_components/ypsilon_local`. Desa una còpia de la carpeta anterior i reinicia HA. Aquesta Alpha conserva `ypsilon_local`; no necessita la migració a `runxin_local`.
2. Si tens una entrada de només diagnòstic del mateix dispositiu, descarrega primer el seu informe i elimina aquesta entrada abans de donar d'alta el dispositiu normalment. No es transforma automàticament en una entrada amb sensors.
3. Afegeix **Runxin Local**, indica la IP local i accepta l'explicació **Alpha amb controls manuals del rellotge validats**. Per defecte llegeix cada minut, sense cadència adaptativa. La correcció automàtica del rellotge està bloquejada encara que hi hagi una opció antiga activada.
4. Compara els sensors amb l'app que funciona. Algunes entitats de diagnòstic estan desactivades per defecte; activa les que necessitis des de la llista d'entitats. No cal canviar ajustos per comparar-los.
5. Des del menú de l'entrada de la integració, **Descarrega els diagnòstics** i adjunta el JSON a la issue existent, juntament amb uns valors o captures de l'app, les unitats i l'hora aproximada. Exportar el diagnòstic no inicia una altra exploració. Oculta dades identificatives a les captures.

L'entrada normal autentica i fa lectures LAN periòdiques; no és una captura passiva. Si l'app i HA interfereixen, pausa les lectures o desactiva temporalment l'entrada mentre fas les captures, sense tornar a aparellar l'equip. Es conserven el domini, la versió de config entry i les identitats existents del G6 i Midnight.

## Què permet

- Sensors d'estat, aigua, durades i diagnòstic amb interpretació **F79D de referència**.
- Sensors equivalents per al rellotge, horari de regeneració, duresa, sal afegida, temps de cabal continu, tall per cabal brut i codi de motiu de tancament.
- Dos bytes originals per camp rebut a `state._rawFieldBytes`, i atributs de referència a les entitats. No s'exporten paquets complets, claus ni sessions.
- Metadades de model, evidència i permisos. Rebre zero o false no demostra que una funció sigui aplicable.

A la **2.9.3**, el **rellotge del dispositiu** i el **botó de sincronització manual** són controls validats disponibles sense activar ajustos experimentals. Conserven els identificadors i la comprovació amb lectura nova. L’alta, les lectures i les recàrregues no inicien escriptures del rellotge. Els altres ajustos requereixen el mode experimental i la regeneració té una segona opció. Serveis administratius, coordinador i adaptador imposen els mateixos permisos per camp; habilitar el camp 4 no permet altres escriptures ni correcció automàtica.

Les lectures numèriques són provisionals i no generen **estadístiques de llarg termini**. HA encara pot desar l'historial ordinari. Les etiquetes enum són de referència, excepte l’idioma confirmat codi 7 → neerlandès; els codis desconeguts es mantenen visibles.

## Comparacions prioritàries

| Camp | Referència del JSON | Què falta confirmar |
|---|---|---|
| 26, resina | `F0 00`, primer byte 240 | Valor, nom i unitat de l'app. HA mostra 240 sense litres ni multiplicador assumit. |
| 41–42, quantitat per cicle | 15 | L’usuari va canviar 24 → 15 a Runxin Advanced → Water treatment capacity. Cal confirmar la unitat i la correspondència amb aquest camp; HA manté 15 sense unitat assumida. |
| 35–36, restant | 1304 L | Capacitat restant amb la seva unitat, prop de l'hora de lectura. |
| 37–40, consum diari/mitjana | 215 / 192 L | Consum del dia i mitjana del controlador; no confondre-la amb un total de l'historial setmanal. |
| 47, duresa | 280 mg/L | Nom exacte i escala de duresa. |
| 43, sal afegida | 25 kg | Registre de sal afegida, no nivell físic del dipòsit. |
| 4/5/10, hores | 20:38 / 00:00 / 00:00 | Rellotge i horari de regeneració visibles. |
| 6/7/15/17/19/21/23 | Proteccions i durades | Comparar els ajustos que l'app mostri, sense modificar-los. |

Totes les unitats són interpretacions de referència pendents de contrast. La resina i la quantitat per cicle no tenen unitat confirmada. Es conserva el segon byte de resina sense deduir un còdec U16. El camp 52 es llegeix amb memòria cau independent i pot ser anterior a la resta de la instantània.

La [issue #17](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6044822202) confirma BL3372 `0x520F`, firmware 62016, autenticació amb l'app tancada, model 1 estable i resposta dels 52 camps en dues consultes sense errors. La fixture conserva només els parells publicats: les trames reconstruïdes són sintètiques. Les proves de programari no validen conversions físiques.

Una calibració futura es farà al model 1, sense canviar les conversions del G6/Midnight. Aquesta Alpha no explora camps superiors al 52; el rellotge manual (camp 4) està verificat a l’equip reportat; la resta d’escriptures opcionals continuen pendents.

## Confirmacions incorporades a la 2.9.3

La [resposta del 10-10-2026](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6096161743) confirma rellotge inicial 11:23, escriptures a 11:24 i 11:26 i restauració amb el botó de sincronització manual. La pantalla del controlador i Water Device coincideixen després de cada acció. Només es va provar el camp 4 i després es va desactivar l’opció experimental. No valida la correcció automàtica ni altres escriptures.

La pantalla física és en neerlandès amb codi d’idioma 7. HA corregeix només aquesta correspondència del model 1, sense escriure l’idioma ni canviar la llengua de l’app.

L’equip té 24 L nominals de resina, però el camp 26 continua `F0 00` (referència 240) i els camps 41–42 continuen en 15. Al frontend del fabricant, `resinVolume` és Resin volume i `periodicWaterProduction` és Water treatment capacity. No hem confirmat independentment quin camp local modificava aquella pantalla de l’app Runxin antiga. `240 / 10 = 24 L` és plausible, però encara no és un contrast amb el valor configurat. Es mantenen les dues lectures sense unitat assumida i no s’aplica el còdec U16 del model 14.

El volum de resina ha de descriure la càrrega real, no ajustar-se al nombre de persones. La capacitat de tractament és un altre paràmetre que depèn de resina, duresa i ajustos de regeneració; reduir-la mantenint els cicles pot fer regenerar més sovint en lloc d’estalviar. Cal aclarir l’etiqueta/unitat i seguir les instruccions de l’equip abans de proposar un canvi. No cal tornar a aparellar, recuperar l’app antiga, repetir diagnòstics ni modificar ajustos per aclarir les lectures.

## Funcionament reportat després de regenerar amb la 2.9.3

La [resposta posterior del 10-10-2026](https://github.com/Danirv/runxin-local/issues/17#issuecomment-6101162421) confirma lectures periòdiques normals i recuperació dels valors després dels reinicis de HA en actualitzar. L’equip reporta model 1, firmware BL3372 62016 i integració 2.9.3.

A les 19:41:45, hora local, HA mostrava aspiració de salmorra i esbandida lenta mentre el controlador indicava **“pekel-spoel traag up-flow”**. Això contrasta aquella fase concreta. HA havia indicat ompliment de salmorra a les 19:35:34, uns sis minuts abans. Amb lectures cada 60 segons, aquesta observació no valida independentment la durada configurada ni demostra un error respecte dels set minuts de la lectura anterior. Els intents avortats anteriors s’exclouen de la validació de seqüència i durades. L’opció de regeneració de HA estava desactivada: no valida l’ordre d’inici del camp 34.

Després del cicle, HA mostrava capacitat restant **3429 L**, davant dels **1267 L** reportats el 8 d’octubre. Es registra una recuperació de capacitat després de regenerar, sense calibració independent de la unitat. Es mantenen duresa 280 mg/L, resina `F0 00` / referència 240 i referència per cicle 15. Si la duresa és expressada com CaCO₃, `3,429 m³ × 28 °f ≈ 96 °f·m³`, uns `4 °f·m³/L` per als 24 L nominals de resina. És una comprovació de coherència, no un contrast amb la resina configurada ni una prova de l’escala 0,1. L’usuari recorda una etiqueta L al costat de l’ajust antic, però no n’està segur; la unitat i la correspondència exacta amb el camp local continuen pendents.

S’incorpora evidència de funcionament i d’una fase, sense canviar Alpha, còdecs, permisos ni unitats provisionals. Les comparacions anteriors són punts de calibració pendents: no es demanen més proves, captures ni diagnòstics a aquest contribuent. La incidència original de connexió/alta es pot tancar independentment d’aquestes validacions.

## Ajustos experimentals opcionals

A l’entrada operativa del model 1, obre **Configuració → Dispositius i serveis → Runxin Local → Configura**. Activa **els ajustos experimentals del model 1** i desa. La recàrrega afegeix controls addicionals per a límit de temps de cabal (6), hora de regeneració (10), sal afegida (43) i duresa (47). **El camp 4 està verificat: escriptures manuals del rellotge i restauració amb sincronització manual. Els camps 6/10/43/47 i la regeneració (34) continuen pendents.** No cal repetir la prova del rellotge ja completada.

Per a una prova nova, anota una lectura inicial nova, canvia un sol ajust una quantitat petita dins del rang, comprova la lectura posterior i la pantalla/app si és visible, restaura el valor original i confirma’l. Aporta camp, valor inicial, sol·licitat, llegit, unitat/pantalla i restauració. No repeteixis una ordre amb resultat ambigu: la integració comprova l’estat sense reenviar-la a cegues.

Una **segona opció** permet iniciar una regeneració prevista i requereix també el mode d’ajustos. El botó comprova servei i vacances desactivades amb una lectura nova, envia camp 34 = 1 una sola vegada i comprova la fase. L’avanç directe de fases continua bloquejat, també als serveis administratius.

El **rellotge automàtic**, el **camp 7**, vacances i escriptures de resina/capacitat continuen bloquejats. El dispositiu va retornar unitat 1; el control de llindar de cabal està calibrat per a unitat 2. Les lectures de resina i capacitat encara són provisionals.

Desactivar els ajustos experimentals elimina només els controls addicionals i desactiva també la prova de regeneració. El rellotge i la sincronització manuals continuen disponibles. Es revoca i substitueix la sessió anterior; es conserven sensors de referència, identificadors, bytes crus i absència d’estadístiques provisionals, també després d’actualitzar o reiniciar. Els diagnòstics separen evidència del model i permisos efectius. Exportar-los no inicia lectures ni escriptures. G6 i models 12/14 mantenen la política.
