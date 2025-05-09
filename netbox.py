from concurrent.futures import ThreadPoolExecutor
from typing import *

from pynetbox.core.api import Api as NetboxAPI
from pynetbox.core.response import Record
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

import config
import utils.common
import utils.netbox
from models.pve import ProxmoxVM, PveDisk, PveInterface as ProxmoxInterface


def populate_vms(api: NetboxAPI, pve_vms: List[ProxmoxVM], pve_nodes: List[str]) -> List[Tuple[NetboxVM, ProxmoxVM]]:
    netbox_hypervisors = [api.dcim.devices.get(name=i, type=config.HYPERVISOR_DEVICE_TYPE) for i in pve_nodes]

    for hypervisor in netbox_hypervisors:
        vms = api.virtualization.virtual_machines.filter(device_id=hypervisor.id)
        vm_zip: List[Tuple[NetboxVM | None, ProxmoxVM | None]] = utils.common.full_outer_join(vms, pve_vms,
                                                                                              lambda x, y: x.serial == y.uuid)

        def _process_single_pair(netbox_vm, proxmox_vm) -> Tuple[NetboxVM, ProxmoxVM] | None:
            if proxmox_vm is None:
                netbox_vm.delete()
                return None
            vm_data = utils.netbox.prepare_vm_data(proxmox_vm, hypervisor)
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
        disk_zip: List[Tuple[Record | None, PveDisk | None]] = utils.common.full_outer_join(netbox_disks, proxmox_disks,
                                                                                            lambda x, y: x.name == y.id)
        for netbox_disk, proxmox_disk in disk_zip:
            if proxmox_disk is None:
                netbox_disk.delete()
                continue

            disk_data = utils.netbox.prepare_disk_data(proxmox_disk, netbox_vm)

            if netbox_disk is None:
                api.virtualization.virtual_disks.create(**disk_data)
                continue

            netbox_disk.update(disk_data)


def populate_interfaces(api: NetboxAPI, vm_pair_list: List[Tuple[NetboxVM, ProxmoxVM]]):
    for netbox_vm, proxmox_vm in vm_pair_list:
        netbox_ifaces = list(api.virtualization.interfaces.filter(virtual_machine_id=netbox_vm.id))
        proxmox_ifaces = proxmox_vm.interfaces
        iface_zip: List[Tuple[Record | None, ProxmoxInterface | None]] = utils.common.full_outer_join(netbox_ifaces, proxmox_ifaces,
                                                                                                      lambda x, y: x.name == y.name)
        for netbox_iface, proxmox_iface in iface_zip:
            if proxmox_iface is None:
                netbox_iface.delete()
                continue

            interface_data = utils.netbox.prepare_interface_data(proxmox_iface, netbox_vm)

            if netbox_iface is None:
                netbox_iface = api.virtualization.interfaces.create(**interface_data)
            else:
                netbox_iface.update(interface_data)

            for proxmox_ip in proxmox_iface.ipv4_addresses + proxmox_iface.ipv6_addresses:
                netbox_ip = api.ipam.ip_addresses.get(address=proxmox_ip)
                ip_data = utils.netbox.prepare_ip_data(proxmox_ip, netbox_iface)

                if not netbox_ip:
                    api.ipam.ip_addresses.create(**ip_data)
                else:
                    netbox_ip.update(ip_data)