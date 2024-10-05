#!/bin/bash -e
SOURCE_DIR="$(cd ${0%/*} ; pwd)"

SOURCE_FILES="${SOURCE_DIR}/src"
PACKAGE_NAME="beacon-agent"
PROGRAM_NAME="beacon_agent"
DIST="${SOURCE_DIR}/dist"
TARGET="${DIST}/${PACKAGE_NAME}"
DATE="$(date +"%Y-%m-%d %H:%M:%S")"
VERSION="$(cat DEBIAN/control | grep Version: | cut -d ' ' -f 2)"

echo "INFO: Building package ${PACKAGE_NAME} with version ${VERSION}"

echo -e "INFO: Cleaning build..."
rm -rf "${DIST}"
rm -rf "${SOURCE_FILES}/__pycache__"
find "${SOURCE_FILES}" -type d -name '__pycache__' -exec rm -rf {} +
mkdir -p "${TARGET}/"

# copy files
echo -e "INFO: Copying files..."
mkdir -p "${TARGET}/usr/share/doc/${PACKAGE_NAME}/"
mkdir -p "${TARGET}/usr/share/man/man1/"
mkdir -p "${TARGET}/usr/bin/"
mkdir -p "${TARGET}/lib/systemd/system"
mkdir -p "${TARGET}/usr/lib/python3/dist-packages/${PROGRAM_NAME}/"
cp -r DEBIAN "${TARGET}/DEBIAN"
cp SYSTEMD/* "${TARGET}/lib/systemd/system/"
cp "${SOURCE_FILES}/beacon_agent_main.py" "${TARGET}/usr/bin/${PACKAGE_NAME}"
cp -r "${SOURCE_FILES}/${PROGRAM_NAME}/"* "${TARGET}/usr/lib/python3/dist-packages/${PROGRAM_NAME}/"

# generate man pages
echo -e "INFO: Generating man pages..."
gzip --best -n -c CHANGELOG > "${TARGET}/usr/share/doc/${PACKAGE_NAME}/changelog.gz"
cp COPYRIGHT "${TARGET}/usr/share/doc/${PACKAGE_NAME}/copyright"
cat MANPAGE | sed "s/__VERSION__/${VERSION}/" | sed "s/__DATE__/${DATE}/" | gzip --best -n > "${TARGET}/usr/share/man/man1/${PACKAGE_NAME}.1.gz"

# fix permissions
echo -e "INFO: Setting permissions..."
find "${TARGET}/" -type d -exec chmod 0755 {} +
find "${TARGET}/" -type f -exec chmod 0644 {} +
chmod 0755 "${TARGET}/DEBIAN/"pre*
chmod 0755 "${TARGET}/DEBIAN/"post*
chmod 0755 "${TARGET}/usr/bin/"*

# now build package
echo -e "INFO: Now building package..."
cd "${DIST}"
dpkg-deb -Zgzip --root-owner-group --build ${PACKAGE_NAME}
mv "${PACKAGE_NAME}.deb" "${PACKAGE_NAME}-${VERSION}.deb"

# and validate the package
echo -e "INFO: Now running lintian..."
lintian --fail-on error,warning -i "${PACKAGE_NAME}-${VERSION}.deb"

echo "INFO: Successfully built ${PACKAGE_NAME}-${VERSION}.deb"
exit 0