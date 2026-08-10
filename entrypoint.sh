#!/bin/sh
set -eu

UNOSERVER_PORT="${UNOSERVER_PORT:-2003}"
UNOSERVER_RESTART_DELAY_SECONDS="${UNOSERVER_RESTART_DELAY_SECONDS:-3}"

unoserver_supervisor() {
    delay="$UNOSERVER_RESTART_DELAY_SECONDS"
    while true; do
        echo "Starting unoserver on port ${UNOSERVER_PORT}"
        start_ts=$(date +%s)
        unoserver --port "${UNOSERVER_PORT}" || true
        elapsed=$(( $(date +%s) - start_ts ))
        echo "unoserver exited after ${elapsed}s, restarting in ${delay}s"
        sleep "$delay"
        if [ "$elapsed" -lt "$delay" ]; then
            delay=$(( delay * 2 > 60 ? 60 : delay * 2 ))
        else
            delay="$UNOSERVER_RESTART_DELAY_SECONDS"
        fi
    done
}

unoserver_supervisor &

exec uvicorn libreoffice_converter.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
