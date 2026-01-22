#!/bin/sh

KEEP="discord"
FILE="/tmp/open_apps"

if [ -f "$FILE" ]; then
    while read name; do
        # ignorar líneas vacías
        [ -z "$name" ] && continue

        # buscar procesos que coincidan parcialmente con el nombre
        for pid in $(ps -eo pid,cmd | grep -i "$name" | grep -v grep | awk '{print $1}'); do
            cmd=$(ps -p "$pid" -o cmd=)

            # si el comando contiene "discord", no lo matamos
            echo "$cmd" | grep -qi "$KEEP" && continue

            kill -9 "$pid"
        done
    done < "$FILE"
fi

rm -f "$FILE"
