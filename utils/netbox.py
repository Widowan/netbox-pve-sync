from typing import Dict, Any

import pynetbox
from pynetbox.core.api import Api as NetboxAPI

from pynetbox.core.response import Record
from pynetbox.models.dcim import Devices as NetboxDevice
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

import config
from models.pve import ProxmoxVM, PveDisk, PveInterface as ProxmoxInterface


def prepare_vm_data(hypervisor: NetboxDevice, pve_vm: ProxmoxVM):
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


def prepare_disk_data(netbox_vm: NetboxVM, proxmox_disk: PveDisk) -> Dict[str, Any]:
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_disk.id,
        'size': proxmox_disk.size // (1024 ** 2)
    }


def prepare_interface_data(netbox_vm: NetboxVM, proxmox_iface: ProxmoxInterface):
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_iface.name,
        'mtu': proxmox_iface.mtu,
        'primary_mac_address': proxmox_iface.mac
    }


def prepare_ip_data(netbox_iface: Record, proxmox_ip: str):
    return {
        'address': proxmox_ip,
        'assigned_object_type': 'virtualization.vminterface',
        'assigned_object_id': netbox_iface.id,
        'status': 'active'
    }


def get_netbox_api() -> NetboxAPI:
    return pynetbox.api(url=config.NB_HOST, token=config.NB_TOKEN)
