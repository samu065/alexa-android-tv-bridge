#!/data/data/com.termux/files/usr/bin/bash
set -e

ADB_TARGET="emulator-5554"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Avvio adb server e verifica device $ADB_TARGET"
adb start-server
if ! adb devices | grep -q "^${ADB_TARGET}[[:space:]]*device$"; then
    echo "ERRORE: $ADB_TARGET non risulta autorizzato. Esegui 'adb devices -l' per controllare lo stato."
    exit 1
fi

cd "$PROJECT_DIR"

echo "==> Avvio server Flask sulla porta 5000 (background)"
nohup python app.py > server.log 2>&1 &
SERVER_PID=$!
echo "Server avviato (PID $SERVER_PID) - log: $PROJECT_DIR/server.log"

sleep 2

echo "==> Avvio Fauxmo (emulazione dispositivi smart per Alexa)"
nohup fauxmo -c fauxmo.conf.json -v > fauxmo.log 2>&1 &
FAUXMO_PID=$!
echo "Fauxmo avviato (PID $FAUXMO_PID) - log: $PROJECT_DIR/fauxmo.log"

sleep 2

echo "==> Avvio watchdog (riavvia fauxmo da solo se si blocca)"
nohup ./watchdog.sh > /dev/null 2>&1 &
WATCHDOG_PID=$!
echo "Watchdog avviato (PID $WATCHDOG_PID) - log: $PROJECT_DIR/watchdog.log"

echo ""
echo "Tutto pronto. Sul dispositivo Alexa (stessa rete Wi-Fi del box) di':"
echo "  \"Alexa, scopri dispositivi\""
echo "Poi comanda con: \"Alexa, accendi Netflix\", \"Alexa, accendi Volume Su\", ecc."
echo ""
echo "PID server: $SERVER_PID | PID fauxmo: $FAUXMO_PID | PID watchdog: $WATCHDOG_PID"
