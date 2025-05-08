import os
from concurrent.futures import ThreadPoolExecutor
from typing import *

import pynetbox
from pynetbox.core.api import Api as NetboxAPI
from pynetbox.core.response import Record
from pynetbox.models.dcim import Devices as NetboxDevice
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

import pve
from pve import ProxmoxVM, Disk as ProxmoxDisk, Interface as ProxmoxInterface

NB_HOST = os.environ["NETBOX_HOST"]
NB_TOKEN = os.environ["NETBOX_TOKEN"]
HYPERVISOR_DEVICE_TYPE = os.environ.get("HYPERVISOR_DEVICE_TYPE", "proxmox-ve")


def __get_netbox_api() -> NetboxAPI:
    return pynetbox.api(url=NB_HOST, token=NB_TOKEN)


def _prepare_vm_data(pve_vm: ProxmoxVM, hypervisor: NetboxDevice):
    return {
        'name': pve_vm.name,
        'status': 'active',
        'serial': pve_vm.uuid,
        'site': hypervisor.site.id,
        'cluster': hypervisor.cluster.id,
        'device': hypervisor.id,
        'vcpus': pve_vm.cpu,
        'memory': pve_vm.ram // (1024 ** 2),
        'custom_fields': {
            'vmid': pve_vm.vmid,
        },
    }


def full_outer_join(first: Iterable, second: Iterable, eq=lambda x, y: x == y) -> List[
    Tuple[object | None, object | None]]:
    result = []
    second_matches = {j: False for j in second}
    for i in first:
        first_matched = False
        for j in second:
            if eq(i, j):
                first_matched = True
                second_matches[j] = True
                result.append((i, j))
        if not first_matched:
            result.append((i, None))
    result.extend((None, k) for k, v in second_matches.items() if not v)
    return result


def populate_vms(api: NetboxAPI, pve_vms: List[ProxmoxVM], pve_nodes: List[str]) -> List[Tuple[NetboxVM, ProxmoxVM]]:
    netbox_hypervisors = [api.dcim.devices.get(name=i, type=HYPERVISOR_DEVICE_TYPE) for i in pve_nodes]

    for hypervisor in netbox_hypervisors:
        vms = api.virtualization.virtual_machines.filter(device_id=hypervisor.id)
        vm_zip: List[Tuple[NetboxVM | None, ProxmoxVM | None]] = full_outer_join(vms, pve_vms,
                                                                                 lambda x, y: x.serial == y.uuid)

        def _process_single_pair(netbox_vm, proxmox_vm) -> Tuple[NetboxVM, ProxmoxVM] | None:
            if proxmox_vm is None:
                netbox_vm.delete()
                return None
            vm_data = _prepare_vm_data(proxmox_vm, hypervisor)
            if netbox_vm is None:
                netbox_vm = api.virtualization.virtual_machines.create(**vm_data)
            else:
                netbox_vm.update(vm_data)
            return netbox_vm, proxmox_vm

        with ThreadPoolExecutor() as executor:
            result = list(executor.map(lambda x: _process_single_pair(x[0], x[1]), vm_zip))
    return result


def populate_disks(api: NetboxAPI, vm_pair_list: List[Tuple[NetboxVM, ProxmoxVM]]):
    for netbox_vm, proxmox_vm in vm_pair_list:
        netbox_disks = list(api.virtualization.virtual_disks.filter(virtual_machine_id=netbox_vm.id))
        proxmox_disks = proxmox_vm.disks
        disk_zip: List[Tuple[Record | None, ProxmoxDisk | None]] = full_outer_join(netbox_disks, proxmox_disks,
                                                                                   lambda x, y: x.name == y.id)
        for netbox_disk, proxmox_disk in disk_zip:
            if proxmox_disk is None:
                netbox_disk.delete()
                continue

            disk_info = {
                'virtual_machine': netbox_vm.id,
                'name': proxmox_disk.id,
                'size': proxmox_disk.size // (1024 ** 2)
            }

            if netbox_disk is None:
                api.virtualization.virtual_disks.create(**disk_info)
                continue

            netbox_disk.update(disk_info)


def populate_interfaces(api: NetboxAPI, vm_pair_list: List[Tuple[NetboxVM, ProxmoxVM]]):
    for netbox_vm, proxmox_vm in vm_pair_list:
        netbox_ifaces = list(api.virtualization.interfaces.filter(virtual_machine_id=netbox_vm.id))
        proxmox_ifaces = proxmox_vm.interfaces
        iface_zip: List[Tuple[Record | None, ProxmoxInterface | None]] = full_outer_join(netbox_ifaces, proxmox_ifaces,
                                                                                         lambda x, y: x.name == y.name)
        for netbox_iface, proxmox_iface in iface_zip:
            if proxmox_iface is None:
                netbox_iface.delete()
                continue

            iface_info = {
                'virtual_machine': netbox_vm.id,
                'name': proxmox_iface.name,
                'mtu': proxmox_iface.mtu,
                'primary_mac_address': proxmox_iface.mac
            }

            if netbox_iface is None:
                netbox_iface = api.virtualization.interfaces.create(**iface_info)
            else:
                netbox_iface.update(iface_info)

            for proxmox_ip in proxmox_iface.ipv4_addresses + proxmox_iface.ipv6_addresses:
                netbox_ip = api.ipam.ip_addresses.get(address=proxmox_ip)
                ip_data = {
                    'address': proxmox_ip,
                    'assigned_object_type': 'virtualization.vminterface',
                    'assigned_object_id': netbox_iface.id,
                    'status': 'active'
                }
                if not netbox_ip:
                    api.ipam.ip_addresses.create(**ip_data)
                else:
                    netbox_ip.update(ip_data)

def main():
    api = __get_netbox_api()
    pve_vms = pve.proxmox_vms()
    pve_nodes = pve.proxmox_nodes()
    vm_list = populate_vms(api, pve_vms, pve_nodes)
    populate_disks(api, vm_list)
    populate_interfaces(api, vm_list)

if __name__ == '__main__':
    main()