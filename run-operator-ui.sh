#!/bin/bash
cd /Volumes/SSD/archive/gov/governance-layer || exit 1
python3 -m http.server 8000 &
sleep 1
open http://localhost:8000/docs/dev/operator-ui-prototype/index.html
wait
