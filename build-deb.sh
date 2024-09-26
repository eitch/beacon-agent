#!/bin/bash -e
SOURCEDIR="$(cd ${0%/*} ; pwd)"

SOURCE_FILES="${SOURCEDIR}/src"
DEB_NAME="beacon-agent"
PROGRAM_NAME="beacon-agent"
DIST="${SOURCEDIR}/dist"
TARGET="${DIST}/${DEB_NAME}"
DATE="$(date +"%Y-%m-%d %H:%M:%S")"
VERSION="$(cat DEBIAN/control | grep Version: | cut -d ' ' -f 2)"

echo "INFO: Building package ${DEB_NAME} with version ${VERSION}"

echo -e "INFO: Cleaning build..."
rm -rf "dist"
rm -f ${TARGET}*
mkdir -p "${TARGET}/"

# copy files
echo -e "INFO: Copying files..."
mkdir -p ${TARGET}/usr/share/doc/${DEB_NAME}/
mkdir -p ${TARGET}/usr/share/man/man1/
mkdir -p ${TARGET}/usr/bin/
mkdir -p ${TARGET}/lib/systemd/system
cp "${SOURCE_FILES}/${PROGRAM_NAME}.py" ${TARGET}/usr/bin/${PROGRAM_NAME}
cp -r DEBIAN ${TARGET}/DEBIAN
cp SYSTEMD/* ${TARGET}/lib/systemd/system/

# generate man pages
echo -e "INFO: Generating man pages..."
gzip --best -n -c CHANGELOG > ${TARGET}/usr/share/doc/${DEB_NAME}/changelog.gz
cp COPYRIGHT ${TARGET}/usr/share/doc/${DEB_NAME}/copyright
cat MANPAGE | sed "s/__VERSION__/${VERSION}/" | sed "s/__DATE__/${DATE}/" | gzip --best -n > ${TARGET}/usr/share/man/man1/${PROGRAM_NAME}.1.gz

# fix permissions
echo -e "INFO: Setting permissions..."
find ${TARGET}/ -type d -exec chmod 0755 {} +
find ${TARGET}/ -type f -exec chmod 0644 {} +
chmod 0755 ${TARGET}/DEBIAN/pre*
chmod 0755 ${TARGET}/DEBIAN/post*
chmod 0755 ${TARGET}/usr/bin/*

# now build package
echo -e "INFO: Now building package..."
cd "${DIST}"
dpkg-deb -Zgzip --root-owner-group --build ${DEB_NAME}
mv "${DEB_NAME}.deb" "${DEB_NAME}-${VERSION}.deb"

# and validate the package
echo -e "INFO: Now running lintian..."
lintian --fail-on error,warning -i ${DEB_NAME}-${VERSION}.deb

echo "INFO: Successfully built ${DEB_NAME}-${VERSION}.deb"
exit 0