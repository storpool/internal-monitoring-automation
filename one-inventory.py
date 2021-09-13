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


def get_ansible_host(server: pyone.OneServer, vm: pyone.bindings.VMSub) -> str:
    """Retrieves the FQDN of the VM or it returns the IP of the first network"""
    if isinstance(vm.TEMPLATE["NIC"], list):
        vm_access_nic = vm.TEMPLATE["NIC"][0]
    else:
        vm_access_nic = vm.TEMPLATE["NIC"]

    ansible_host = None

    if "IP" in vm_access_nic:
        ansible_host = vm_access_nic["IP"]

    vm_virtual_network = server.vn.info(int(vm_access_nic["NETWORK_ID"]))

    if "DOMAIN" in vm_virtual_network.TEMPLATE:
        ansible_host = vm.NAME + "." + vm_virtual_network.TEMPLATE["DOMAIN"][:-1]

    return ansible_host


def get_vm_info(server: pyone.OneServer, vm: pyone.bindings.VMSub) -> dict:
    """Returns a dict for a specified VM"""
    vm_info = dict(id=vm.ID, ansible_user="root", state=vm.STATE)

    ansible_host = get_ansible_host(server, vm)

    if ansible_host is not None:
        vm_info["ansible_host"] = ansible_host

    if "ANSIBLE_USER" in vm.USER_TEMPLATE:
        vm_info["ansible_user"] = vm.USER_TEMPLATE["ANSIBLE_USER"]

    return vm_info


def get_single_host(server: pyone.OneServer, hostname: str) -> dict:
    """Returns a single host"""
    vm_pool = get_all_vms(server)
    return get_vm_info(server, [vm.ID for vm in vm_pool.VM if vm.NAME == hostname][0])


def get_inventory(server: pyone.OneServer) -> str:
    """Returns a JSON string containing all VMs"""
    vm_pool = get_all_vms(server)
    inventory = {"_meta":
        {
            "hostvars": {}
        }
    }
    for vm in vm_pool.VM:
        inventory["_meta"]["hostvars"][vm.NAME] = get_vm_info(server, vm)

    return to_json(inventory)


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
    group.add_argument('--list', action='store_true', help="List active VMs")
    group.add_argument('--host', help="List details about a specific VM")

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
            print(get_inventory(one_server))
        elif args.host:
            print(to_json(get_single_host(one_server, args.host)))
    except pyone.OneException as error:
        sys.stderr.write("%s\n" % error.message)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
