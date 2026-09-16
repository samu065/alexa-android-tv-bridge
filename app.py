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
    "play_pause": "85",     # KEYCODE_MEDIA_PLAY_PAUSE
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


@app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json(silent=True) or {}
    app_name = data.get("app_name")
    command = data.get("command")

    if not app_name and not command:
        return jsonify({"error": "Richiesto 'app_name' o 'command' nel body JSON"}), 400

    try:
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
