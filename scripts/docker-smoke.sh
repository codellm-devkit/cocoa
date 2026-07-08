#!/usr/bin/env bash
# Build the image and prove it can map a real (tiny) project end-to-end.
set -euo pipefail
cd "$(dirname "$0")/.."

docker build -t cocoa:dev .
docker run --rm cocoa:dev --help >/dev/null

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
cp -r test/fixtures/pysmoke/. "${workdir}/"

docker run --rm -v "${workdir}:/work" cocoa:dev map -p /work
test -f "${workdir}/.cocoa/system-graph.json"
grep -q "pysmoke\|work" "${workdir}/.cocoa/SYSTEM_REPORT.md"
echo "docker smoke OK"
