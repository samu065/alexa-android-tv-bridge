from flask import Flask, request, jsonify
import base64
import json
import os
import subprocess
import logging
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Credenziali del controllo remoto HTTP di Kodi: tenute fuori dal codice
# (file escluso da git, vedi .gitignore) per non finire nel repo pubblico.
# Copia kodi_credentials.json.example e compila i tuoi valori.
_KODI_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "kodi_credentials.json")
with open(_KODI_CREDENTIALS_PATH) as _f:
    _kodi_credentials = json.load(_f)
KODI_USER = _kodi_credentials["user"]
KODI_PASSWORD = _kodi_credentials["password"]

ADB_BIN = "adb"
# "emulator-5554" e' l'alias con cui l'adb server rileva automaticamente
# l'adbd in loopback su questo box (porta 5555): e' gia' autorizzato in modo
# permanente, a differenza di un "adb connect 127.0.0.1:5555" esplicito, che
# su questa ROM richiede una nuova autorizzazione via popup ad ogni sessione.
ADB_TARGET = "emulator-5554"

# Mappa nome app (case-insensitive) -> package Android da lanciare con monkey
# Package verificati con `adb shell pm list packages` sul box in uso
APP_PACKAGES = {
    "netflix": "com.netflix.ninja",
    "youtube": "com.google.android.youtube.tv",
    "prime video": "com.amazon.amazonvideo.livingroom",
    "spotify": "com.spotify.tv.android",
    "dazn": "com.dazn",
    "mediaset infinity": "it.mediaset.infinitytv",
    "rai play": "it.rainet.androidtv",
    "hotstar": "in.startv.hotstar",
    "sony liv": "com.sonyliv",
    "kodi": "org.xbmc.kodi",
}

# Mappa comando -> keycode Android (adb shell input keyevent)
KEY_COMMANDS = {
    "power_sleep": "223",   # KEYCODE_SLEEP
    "power_wake": "224",    # KEYCODE_WAKEUP
    "volume_up": "24",      # KEYCODE_VOLUME_UP
    "volume_down": "25",    # KEYCODE_VOLUME_DOWN
    "mute": "164",          # KEYCODE_VOLUME_MUTE
    "home": "3",            # KEYCODE_HOME
    "back": "4",            # KEYCODE_BACK
    "menu": "82",           # KEYCODE_MENU
    "up": "19",             # KEYCODE_DPAD_UP
    "down": "20",           # KEYCODE_DPAD_DOWN
    "left": "21",           # KEYCODE_DPAD_LEFT
    "right": "22",          # KEYCODE_DPAD_RIGHT
    "select": "23",         # KEYCODE_DPAD_CENTER
    "play_pause": "85",     # KEYCODE_MEDIA_PLAY_PAUSE
    "stop": "86",           # KEYCODE_MEDIA_STOP
    "next": "87",           # KEYCODE_MEDIA_NEXT
    "previous": "88",       # KEYCODE_MEDIA_PREVIOUS
    "rewind": "89",         # KEYCODE_MEDIA_REWIND
    "fast_forward": "90",   # KEYCODE_MEDIA_FAST_FORWARD
}

# Mappa nome addon Kodi (case-insensitive) -> addon id
# Richiede "Consenti controllo remoto via HTTP" attivo in Kodi
# (Impostazioni > Servizi > Controllo), altrimenti la porta 8080 non risponde.
KODI_JSONRPC_URL = "http://127.0.0.1:8080/jsonrpc"
KODI_ADDONS = {
    "mandrakodi": "plugin.video.mandrakodi",
    "stream4me": "plugin.video.s4me",
}

# Mappa nome livello volume -> indice sullo stream STREAM_MUSIC (scala 0-15 su questo box,
# verificata con "adb shell dumpsys audio"). Impostato con "adb shell media volume --stream 3 --set".
VOLUME_LEVELS = {
    "volume 25": 4,
    "volume 50": 8,
    "volume 75": 11,
    "volume 100": 15,
}


def run_adb(args):
    """Esegue un comando adb verso ADB_TARGET. Solleva eccezione se fallisce."""
    full_cmd = [ADB_BIN, "-s", ADB_TARGET] + args
    logger.info("Eseguo: %s", " ".join(full_cmd))
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout.strip()


def run_kodi_addon(addon_id):
    """Porta Kodi in primo piano e lancia un addon via JSON-RPC (Addons.ExecuteAddon)."""
    run_adb(["shell", "monkey", "-p", "org.xbmc.kodi", "-c", "android.intent.category.LAUNCHER", "1"])
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.ExecuteAddon",
        "params": {"addonid": addon_id},
        "id": 1,
    }).encode("utf-8")
    auth = base64.b64encode(f"{KODI_USER}:{KODI_PASSWORD}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        KODI_JSONRPC_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json(silent=True) or {}
    app_name = data.get("app_name")
    command = data.get("command")
    kodi_addon = data.get("kodi_addon")
    volume_level = data.get("volume_level")

    if not app_name and not command and not kodi_addon and not volume_level:
        return jsonify({
            "error": "Richiesto 'app_name', 'command', 'kodi_addon' o 'volume_level' nel body JSON",
        }), 400

    try:
        if volume_level:
            key = str(volume_level).strip().lower()
            index = VOLUME_LEVELS.get(key)
            if index is None:
                return jsonify({
                    "error": f"Livello volume '{volume_level}' non mappato",
                    "available": sorted(VOLUME_LEVELS),
                }), 404

            run_adb(["shell", "media", "volume", "--stream", "3", "--set", str(index), "--show"])
            return jsonify({"status": "ok", "action": "volume_level", "level": key, "index": index}), 200

        if kodi_addon:
            key = str(kodi_addon).strip().lower()
            addon_id = KODI_ADDONS.get(key)
            if not addon_id:
                return jsonify({
                    "error": f"Addon Kodi '{kodi_addon}' non mappato",
                    "available": sorted(KODI_ADDONS),
                }), 404

            try:
                run_kodi_addon(addon_id)
            except (urllib.error.URLError, TimeoutError) as e:
                return jsonify({
                    "error": "Impossibile contattare Kodi via JSON-RPC",
                    "details": str(e),
                    "hint": "Verifica che in Kodi sia attivo Impostazioni > Servizi > Controllo > "
                            "'Consenti controllo remoto via HTTP'",
                }), 502
            return jsonify({"status": "ok", "action": "kodi_addon", "addon": key, "addon_id": addon_id}), 200

        if app_name:
            key = str(app_name).strip().lower()
            package = APP_PACKAGES.get(key)
            if not package:
                return jsonify({
                    "error": f"App '{app_name}' non mappata",
                    "available": sorted(APP_PACKAGES),
                }), 404

            run_adb(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])
            return jsonify({"status": "ok", "action": "launch_app", "app": key, "package": package}), 200

        key = str(command).strip().lower()
        keycode = KEY_COMMANDS.get(key)
        if not keycode:
            return jsonify({
                "error": f"Comando '{command}' non mappato",
                "available": sorted(KEY_COMMANDS),
            }), 404

        run_adb(["shell", "input", "keyevent", keycode])
        return jsonify({"status": "ok", "action": "command", "command": key}), 200

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout durante l'esecuzione del comando ADB"}), 504
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Errore nell'esecuzione del comando ADB", "details": e.stderr.strip()}), 502
    except FileNotFoundError:
        return jsonify({"error": "Binario 'adb' non trovato nel PATH"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
