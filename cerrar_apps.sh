#!/bin/sh

# ============================
#  CERRAR RETROARCH
# ============================
if pgrep -x "retroarch" > /dev/null; then
    echo "[M-OS] Cerrando RetroArch..."
    pkill -TERM -x "retroarch"
    sleep 1
    pkill -9 -x "retroarch" 2>/dev/null
fi

FILE="/tmp/open_apps"

# ============================
#  PROCESAR ARCHIVO open_apps
# ============================
if [ -f "$FILE" ]; then
    while read name; do
        [ -z "$name" ] && continue

        # ============================
        #  CASO ESPECIAL: WAYDROID
        # ============================
        if echo "$name" | grep -qi "waydroid"; then
            echo "[M-OS] Deteniendo sesión de Waydroid..."
            waydroid session stop
            continue
        fi

        # ============================
        #  CASO ESPECIAL: DISCORD (FLATPAK)
        # ============================
        if echo "$name" | grep -qi "discord"; then
            echo "[M-OS] Cerrando Discord limpiamente..."
            flatpak kill com.discordapp.Discord 2>/dev/null || true
            sleep 1
            continue
        fi

        # ============================
        #  CASO ESPECIAL: DOCKER
        # ============================
        if echo "$name" | grep -qi "docker"; then
            echo "[M-OS] Deteniendo contenedores Docker..."

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

        # ============================
        #  PROCESOS NORMALES
        # ============================
        for pid in $(pgrep -f "$name"); do
            [ "$pid" = "$$" ] && continue  # No matarse a sí mismo
            echo "[M-OS] Terminando proceso: $pid ($name)"
            kill -9 "$pid" 2>/dev/null
        done

    done < "$FILE"
fi

rm -f "$FILE"
