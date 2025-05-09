from typing import Dict, Any

import pynetbox
from pynetbox.core.api import Api as NetboxAPI

from pynetbox.core.response import Record
from pynetbox.models.dcim import Devices as NetboxDevice
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

import config
from config import EXTERNAL_FIELD_SLUG
from models.pve import ProxmoxVM, PveDisk, PveInterface as ProxmoxInterface


def prepare_vm_data(hypervisor: NetboxDevice, pve_vm: ProxmoxVM) -> dict[str, Any]:
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
            EXTERNAL_FIELD_SLUG: True,
        },
    }


def prepare_disk_data(netbox_vm: NetboxVM, proxmox_disk: PveDisk) -> Dict[str, Any]:
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_disk.id,
        'size': proxmox_disk.size // (1024 ** 2),
        'custom_fields': {
            EXTERNAL_FIELD_SLUG: True
        }
    }


def prepare_interface_data(netbox_vm: NetboxVM, proxmox_iface: ProxmoxInterface) -> Dict[str, Any]:
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_iface.name,
        'mtu': proxmox_iface.mtu,
        'primary_mac_address': proxmox_iface.mac,
        'enabled': proxmox_iface.state,
        'custom_fields': {
            EXTERNAL_FIELD_SLUG: True
        }
    }


def prepare_ip_data(netbox_iface: Record, proxmox_ip: str) -> Dict[str, Any]:
    return {
        'address': proxmox_ip,
        'assigned_object_type': 'virtualization.vminterface',
        'assigned_object_id': netbox_iface.id,
        'status': 'active',
        'custom_fields': {
            EXTERNAL_FIELD_SLUG: True
        }
    }

def prepare_primary_ip_patch(primary_ipv4: Record | None, primary_ipv6: Record | None) -> Dict[str, Any]:
    return {
        'primary_ipv4': primary_ipv4.id if primary_ipv4 else None,
        'primary_ipv6': primary_ipv6.id if primary_ipv6 else None,
    }

def get_netbox_api() -> NetboxAPI:
    return pynetbox.api(url=config.NETBOX_HOST, token=config.NETBOX_TOKEN)
