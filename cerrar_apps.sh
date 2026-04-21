#!/bin/sh

if pgrep -x "retroarch" > /dev/null; then
    echo "[M-OS] Cerrando RetroArch..."
    pkill -TERM -x "retroarch"
    sleep 1
    pkill -9 -x "retroarch" 2>/dev/null
fi

FILE="/tmp/open_apps"

if [ -f "$FILE" ]; then
    while read name; do
        [ -z "$name" ] && continue

        # Caso especial: waydroid (se queda como estaba)
        if echo "$name" | grep -qi "waydroid"; then
            echo "[M-OS] Deteniendo sesión de Waydroid..."
            waydroid session stop
            continue
        fi

        for pid in $(pgrep -f "$name"); do
            [ "$pid" = "$$" ] && continue 
            echo "[M-OS] Terminando proceso: $pid ($name)"
            kill -9 "$pid" 2>/dev/null
        done
    done < "$FILE"
fi

rm -f "$FILE"