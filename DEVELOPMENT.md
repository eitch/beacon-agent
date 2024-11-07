# Development

## New version

Update the version in the following files:
* setup.py
* beacon_agent/__init__.py

For a new changelog date:

    date -R -u

Add a change log entry in `CHANGELOG`

Now build the debian package:

    ./build-deb.sh

Now tag the version and create a new release on GitHub
