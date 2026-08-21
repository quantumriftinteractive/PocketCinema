#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketStremio
if [ -f "$BASE_DIR/config/button-diagnostic.mode" ]; then
  exec "$BASE_DIR/experiments/button-diagnostic.sh"
fi
if [ -f "$BASE_DIR/config/ffplay-subtitle-experiment.mode" ]; then
  exec "$BASE_DIR/experiments/ffplay-subtitle-experiment.sh"
fi
exec "$BASE_DIR/client/pocketstremio-ui.sh"
