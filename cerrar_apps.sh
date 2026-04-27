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

        # Caso especial: waydroid
        if echo "$name" | grep -qi "waydroid"; then
            echo "[M-OS] Deteniendo sesión de Waydroid..."
            waydroid session stop
            continue
        fi

        # 🔥 Caso especial: DOCKER
        if echo "$name" | grep -qi "docker"; then
            echo "[M-OS] Deteniendo contenedores Docker..."

            # Apagar contenedores activos
            CONTAINERS=$(docker ps -q)
            if [ -n "$CONTAINERS" ]; then
                docker stop $CONTAINERS
                sleep 1
                docker kill $CONTAINERS 2>/dev/null
            fi

            echo "[M-OS] Matando procesos Docker..."
            pkill -9 dockerd 2>/dev/null
            pkill -9 containerd 2>/dev/null
            pkill -9 containerd-shim 2>/dev/null

            continue
        fi

        # Procesos normales
        for pid in $(pgrep -f "$name"); do
            [ "$pid" = "$$" ] && continue 
            echo "[M-OS] Terminando proceso: $pid ($name)"
            kill -9 "$pid" 2>/dev/null
        done
    done < "$FILE"
fi

rm -f "$FILE"
