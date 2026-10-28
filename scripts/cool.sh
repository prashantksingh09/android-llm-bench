#!/data/data/com.termux/files/usr/bin/bash
# Wait until the battery is at or below a target temperature (°C) before the next run.
# Usage: bash ~/lab/scripts/cool.sh 31   (default 31)
target=${1:-31}
while true; do
  t=$(termux-battery-status | jq -r '.temperature')
  if awk -v t="$t" -v g="$target" 'BEGIN { exit !(t <= g) }'; then
    echo "battery ${t}°C - go"
    break
  fi
  echo "battery ${t}°C - cooling to ${target}°C..."
  sleep 30
done
