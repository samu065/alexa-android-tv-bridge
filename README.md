# Alexa → Android TV Bridge

Server Flask che gira in Termux sul box Android TV e inoltra comandi ricevuti via HTTP al sistema Android tramite ADB in loopback, target `emulator-5554` (così l'adb server rileva in automatico l'adbd in loopback sulla porta 5555 su questo box — su questa ROM un `adb connect 127.0.0.1:5555` esplicito risulta invece `unauthorized` ad ogni sessione). L'integrazione con Alexa avviene tramite **Fauxmo**, che emula dispositivi smart (stile Wemo) scopribili in locale dall'Echo, senza bisogno di skill Alexa, AWS o esporre nulla su internet.

## Setup Termux

```bash
pkg update && pkg upgrade -y
pkg install python android-tools -y
pip install -r requirements.txt
```

## Avvio

```bash
chmod +x start_fauxmo.sh
./start_fauxmo.sh
```

Lo script:
1. avvia l'adb server e verifica che `emulator-5554` risulti autorizzato (`adb devices -l`);
2. avvia `app.py` in background sulla porta 5000 (log in `server.log`);
3. avvia `fauxmo` in background con la configurazione in `fauxmo.conf.json` (log in `fauxmo.log`), che espone un dispositivo smart per ogni app/comando mappato.

Se al primo avvio `emulator-5554` non risulta ancora autorizzato, esegui `adb devices -l` manualmente: la prima volta Android mostra un popup sullo schermo della TV da accettare (idealmente con "Consenti sempre da questo computer").

**Requisiti di rete**: l'Echo Alexa deve trovarsi sulla stessa rete Wi-Fi del box Android TV (Fauxmo funziona via UPnP/SSDP locale, nessuna porta va aperta su internet).

**Prima esecuzione**: dopo aver avviato lo script, di' *"Alexa, scopri dispositivi"*. Alexa troverà i dispositivi definiti in `fauxmo.conf.json` (Netflix, YouTube, Prime Video, Volume Su, ecc.). Da quel momento puoi comandare con *"Alexa, accendi Netflix"*, *"Alexa, accendi Volume Su"*, ecc. (Fauxmo usa la semantica on/off di uno smart plug: "accendi" = esegui l'azione).

Se cambi/aggiungi voci in `fauxmo.conf.json` (nuova app o nuovo comando), ridì *"Alexa, scopri dispositivi"* per farle rilevare.

**Battery/Doze**: su Android, disattiva l'ottimizzazione batteria per Termux ed esegui `termux-wake-lock` prima di avviare lo script, altrimenti il sistema può killare il processo in background dopo un po'.

## Endpoint Flask (per test manuali o estensioni future)

`POST /execute`

```json
{ "app_name": "netflix" }
```

oppure

```json
{ "command": "volume_up" }
```

Test rapido da Termux mentre il server è attivo:

```bash
curl -X POST http://127.0.0.1:5000/execute -H "Content-Type: application/json" -d '{"app_name":"netflix"}'
```

App disponibili: `netflix`, `youtube`, `prime video`, `spotify`, `dazn`, `mediaset infinity`, `rai play`, `hotstar`, `sony liv`, `kodi`.
Comandi disponibili: `power_sleep`, `power_wake`, `volume_up`, `volume_down`, `mute`, `home`, `back`, `play_pause`.

## Alternativa: esposizione pubblica con ngrok

Se in futuro serve richiamare l'endpoint da fuori la rete locale (es. IFTTT, Voice Monkey, skill Alexa custom con endpoint HTTPS), è disponibile anche `start_server.sh`, che avvia `app.py` e apre un tunnel ngrok stampando l'URL pubblico. Richiede `pkg install curl` e il binario ngrok (non nei repo Termux, va scaricato da ngrok.com e autenticato con `ngrok config add-authtoken <TOKEN>`).
