from flask import Flask, request, jsonify
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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

# Mappa nome (case-insensitive) -> URL da aprire con il browser/handler di default
# (es. adb shell am start -a android.intent.action.VIEW -d "<url>")
URL_BOOKMARKS = {}


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


@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json(silent=True) or {}
    app_name = data.get("app_name")
    command = data.get("command")
    url_name = data.get("url_name")

    if not app_name and not command and not url_name:
        return jsonify({"error": "Richiesto 'app_name', 'command' o 'url_name' nel body JSON"}), 400

    try:
        if url_name:
            key = str(url_name).strip().lower()
            url = URL_BOOKMARKS.get(key)
            if not url:
                return jsonify({
                    "error": f"Link '{url_name}' non mappato",
                    "available": sorted(URL_BOOKMARKS),
                }), 404

            run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])
            return jsonify({"status": "ok", "action": "open_url", "url_name": key, "url": url}), 200

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
