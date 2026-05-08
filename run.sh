#!/bin/bash
# Launch MetaKill
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/metakill.py"
