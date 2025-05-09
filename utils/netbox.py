from typing import Dict, Any

from pynetbox.core.response import Record
from pynetbox.models.dcim import Devices as NetboxDevice
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

from models.pve import ProxmoxVM, PveDisk, PveInterface as ProxmoxInterface


def prepare_vm_data(pve_vm: ProxmoxVM, hypervisor: NetboxDevice):
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


def prepare_disk_data(proxmox_disk: PveDisk, netbox_vm: NetboxVM) -> Dict[str, Any]:
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_disk.id,
        'size': proxmox_disk.size // (1024 ** 2)
    }


def prepare_interface_data(proxmox_iface: ProxmoxInterface, netbox_vm: NetboxVM):
    return {
        'virtual_machine': netbox_vm.id,
        'name': proxmox_iface.name,
        'mtu': proxmox_iface.mtu,
        'primary_mac_address': proxmox_iface.mac
    }


def prepare_ip_data(proxmox_ip: str, netbox_iface: Record):
    return {
        'address': proxmox_ip,
        'assigned_object_type': 'virtualization.vminterface',
        'assigned_object_id': netbox_iface.id,
        'status': 'active'
    }
