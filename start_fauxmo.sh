#!/data/data/com.termux/files/usr/bin/bash
set -e

ADB_TARGET="127.0.0.1:5555"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Connessione ADB a $ADB_TARGET"
adb connect "$ADB_TARGET"

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

echo ""
echo "Tutto pronto. Sul dispositivo Alexa (stessa rete Wi-Fi del box) di':"
echo "  \"Alexa, scopri dispositivi\""
echo "Poi comanda con: \"Alexa, accendi Netflix\", \"Alexa, accendi Volume Su\", ecc."
echo ""
echo "PID server: $SERVER_PID | PID fauxmo: $FAUXMO_PID"
