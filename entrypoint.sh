#!/bin/sh
set -eu

UNOSERVER_PORT="${UNOSERVER_PORT:-2003}"
UNOSERVER_RESTART_DELAY_SECONDS="${UNOSERVER_RESTART_DELAY_SECONDS:-3}"

unoserver_supervisor() {
    while true; do
        echo "Starting unoserver on port ${UNOSERVER_PORT}"
        unoserver --port "${UNOSERVER_PORT}" || true
        echo "unoserver exited, restarting in ${UNOSERVER_RESTART_DELAY_SECONDS}s"
        sleep "${UNOSERVER_RESTART_DELAY_SECONDS}"
    done
}

unoserver_supervisor &

exec uvicorn libreoffice_converter.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
