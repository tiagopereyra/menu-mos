#!/bin/sh

FILE="/tmp/open_apps"

if [ -f "$FILE" ]; then
    while read name; do
        [ -z "$name" ] && continue

        # Buscar procesos cuyo comando contenga el nombre
        for pid in $(ps w | grep -i "$name" | grep -v grep | awk '{print $1}'); do
            # Obtener comando completo
            cmd=$(ps w | grep "^[ ]*$pid " | awk '{$1=""; print $0}')

            kill -9 "$pid"
        done
    done < "$FILE"
fi

rm -f "$FILE"
