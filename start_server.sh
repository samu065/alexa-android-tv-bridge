#!/data/data/com.termux/files/usr/bin/bash
set -e

ADB_TARGET="127.0.0.1:5555"
SERVER_PORT=5000
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Connessione ADB a $ADB_TARGET"
adb connect "$ADB_TARGET"

echo "==> Avvio server Flask sulla porta $SERVER_PORT (background)"
cd "$PROJECT_DIR"
nohup python app.py > server.log 2>&1 &
SERVER_PID=$!
echo "Server avviato (PID $SERVER_PID) - log: $PROJECT_DIR/server.log"

sleep 2

echo "==> Avvio tunnel ngrok sulla porta $SERVER_PORT"
nohup ngrok http "$SERVER_PORT" --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

echo "Attendo che ngrok esponga l'URL pubblico..."
sleep 4

PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -n1 | cut -d'"' -f4)

if [ -n "$PUBLIC_URL" ]; then
    echo "==> URL pubblico ngrok: $PUBLIC_URL"
else
    echo "Impossibile recuperare automaticamente l'URL ngrok. Controlla $PROJECT_DIR/ngrok.log o http://127.0.0.1:4040"
fi

echo "PID server: $SERVER_PID | PID ngrok: $NGROK_PID"
