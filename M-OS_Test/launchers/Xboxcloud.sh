#!/bin/bash

flatpak run com.google.Chrome \
  --ozone-platform=wayland \
  --enable-features=UseOzonePlatform \
  --kiosk \
  --app="https://www.xbox.com/play"
