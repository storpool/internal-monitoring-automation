#!/usr/bin/python3
"""
This script is used to retrieve VMs from OpenNebula and to
produce an AWX compatible dynamic inventory
"""
import argparse
import json
import logging
import os
import sys

import pyone

logger = logging.getLogger("OpenNebulaSource")


def get_all_vms(server: pyone.OneServer) -> pyone.bindings.VM_POOLSub:
    """Return ALL VMs excluding those in state DONE"""
    return server.vmpool.info(-2, -1, -1, -1)

def get_vm_info(server: pyone.OneServer, name: str) -> dict:
    """Returns a dict for a specified VM"""

def get_vmpool_info(server: pyone.OneServer) -> str:
    """Returns a JSON string containing all VMs"""


def to_json(in_dict):
    """Return a JSON representation of a dict"""
    return json.dumps(in_dict, sort_keys=True, indent=2)


def getargs() -> argparse.Namespace:
    """Parses Ansible arguments"""
    parser = argparse.ArgumentParser(
        description="""OpenNebula Inventory Module""",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true', help='List active VMs')
    group.add_argument('--host', help='List details about a specific VM')

    return parser.parse_args()


def main() -> None:
    """Main function"""
    args = getargs()

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

    try:
        if args.list:
            print(get_vmpool_info(one_server))
        elif args.host:
            print(to_json(get_vm_info(one_server, args.host)))
    except pyone.OneException as error:
        sys.stderr.write("%s\n" % error.message)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
