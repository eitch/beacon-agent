#!/bin/bash -e
SOURCE_DIR="$(cd ${0%/*} ; pwd)"
cd "${SOURCE_DIR}"

./build-deb.sh
./build-dist.sh

exit 0