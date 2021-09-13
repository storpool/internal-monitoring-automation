#!/usr/bin/python3
"""
This script is used to retrieve VMs from OpenNebula and to
produce an AWX compatible dynamic inventory
"""
import logging
import os

import pyone

logger = logging.getLogger("OpenNebulaSource")


def main() -> None:
    """Main function"""

    logging.basicConfig(level=logging.INFO)

    one_url = os.environ.get("ONE_URL", None)
    one_username = os.environ.get("ONE_USERNAME", None)
    one_password = os.environ.get("ONE_PASSWORD", None)

    if one_url is None:
        raise RuntimeError("ONE_URL environment variable must be set")

    if one_username is None:
        raise RuntimeError("ONE_USERNAME environment variable must be set")

    if one_password is None:
        raise RuntimeError("ONE_PASSWORD environment variable must be set")

    logging.debug("ONE Endpoint: %s ONE Username: %s", one_url, one_username)

    one_server = pyone.OneServer(
        one_url, session=one_username + ":" + one_password
    )

    vm_info = one_server.vmpool.info(-2, -1, -1, -1)
    print("%r", vm_info)


if __name__ == "__main__":
    main()
