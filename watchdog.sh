#!/data/data/com.termux/files/usr/bin/bash
# Tiene sotto controllo fauxmo e lo riavvia da solo se si blocca.
#
# Il bug osservato: dopo una riconnessione Wi-Fi (es. box spento/riacceso),
# il socket di ascolto di fauxmo puo' restare "vivo" ma rotto (asyncio va in
# loop su OSError: Invalid argument su accept()), quindi Alexa non riesce
# piu' a mandare comandi anche se il processo risulta ancora in esecuzione.
# Qui lo rileviamo con un controllo di connessione reale su una delle porte
# dei dispositivi, non solo controllando che il processo sia vivo.

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

LOCK_FILE="watchdog.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Watchdog gia' in esecuzione, esco."
    exit 1
fi

CHECK_PORT=12340       # porta del dispositivo "Netflix", usata come sonda
CHECK_INTERVAL=60      # secondi tra un controllo e l'altro
LOG_MAX_BYTES=5000000  # oltre questa soglia il log e' quasi certamente un loop di errori
WATCHDOG_LOG="watchdog.log"
FAUXMO_MATCH="fauxmo -c fauxmo.conf.json"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$WATCHDOG_LOG"
}

lan_ip() {
    ifconfig wlan0 2>/dev/null | awk '/inet /{print $2}' | head -n1
}

port_is_healthy() {
    # fauxmo si lega all'IP LAN del box (ip_address "auto" in fauxmo.conf.json),
    # non a 127.0.0.1: il check deve puntare li', non al loopback.
    local ip
    ip="$(lan_ip)"
    [ -n "$ip" ] || return 1
    timeout 3 bash -c "echo > /dev/tcp/$ip/$CHECK_PORT" 2>/dev/null
}

start_fauxmo() {
    : > fauxmo.log
    nohup fauxmo -c fauxmo.conf.json -v > fauxmo.log 2>&1 < /dev/null &
    disown
}

restart_fauxmo() {
    log "Riavvio fauxmo (motivo: $1)"
    pkill -9 -f "$FAUXMO_MATCH" 2>/dev/null
    sleep 2
    start_fauxmo
    sleep 5
}

log "Watchdog avviato (PID $$)"

# Grazia iniziale: con ~29 dispositivi il binding di tutte le porte di fauxmo
# puo' richiedere piu' di qualche secondo, altrimenti il primo controllo
# rischia di scattare come falso positivo e riavviare inutilmente.
sleep 20

while true; do
    if ! pgrep -f "$FAUXMO_MATCH" > /dev/null; then
        restart_fauxmo "processo non attivo"
    elif [ -f fauxmo.log ] && [ "$(stat -c %s fauxmo.log 2>/dev/null || echo 0)" -gt "$LOG_MAX_BYTES" ]; then
        restart_fauxmo "log fauxmo troppo grande, probabile loop di errori"
    elif ! port_is_healthy; then
        sleep 2
        if ! port_is_healthy; then
            restart_fauxmo "porta $CHECK_PORT non risponde"
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
