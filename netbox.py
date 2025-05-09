from typing import TypeVar, Iterable, Callable, List, Tuple, Dict

from pynetbox.core.api import Api as NetboxAPI
from pynetbox.core.endpoint import Endpoint as NetboxEndpoint
from pynetbox.core.response import Record as NetboxRecord, RecordSet as NetboxRecordSet
from pynetbox.models.virtualization import VirtualMachines as NetboxVM

import config
from utils.netbox import prepare_interface_data, prepare_ip_data, prepare_vm_data, prepare_disk_data
from models.pve import ProxmoxVM
from utils.common import full_outer_join

T = TypeVar('T')
U = TypeVar('U')

def upsert_pairs(
        netbox_entities: Iterable[T],
        proxmox_entities: Iterable[U],
        match_function: Callable[[T, U], bool],
        netbox_data_function: Callable[[U], Dict],
        api: NetboxEndpoint,
) -> List[Tuple[T, U]]:
    result = []
    entity_pairs = full_outer_join(netbox_entities, proxmox_entities, match_function)

    for netbox_entity, proxmox_entity in entity_pairs:
        if proxmox_entity is None:
            netbox_entity.delete()

        netbox_entity_data = netbox_data_function(proxmox_entity)

        if netbox_entity is None:
            netbox_entity = api.create(**netbox_entity_data)
        else:
            netbox_entity.update(netbox_entity_data)

        result.append((netbox_entity, proxmox_entity))
    return result


def sync_vms(api: NetboxAPI, pve_vms: List[ProxmoxVM], pve_nodes: List[str]) -> List[Tuple[NetboxVM, ProxmoxVM]]:
    result = []
    netbox_hypervisors = [api.dcim.devices.get(name=i, type=config.HYPERVISOR_DEVICE_TYPE) for i in pve_nodes]

    for hypervisor in netbox_hypervisors:
        netbox_vms: Iterable[NetboxVM] = api.virtualization.virtual_machines.filter(device_id=hypervisor.id)
        pairs = upsert_pairs(
            netbox_entities=netbox_vms,
            proxmox_entities=pve_vms,
            match_function=lambda x, y: x.serial == y.uuid,
            netbox_data_function=lambda y: prepare_vm_data(hypervisor, y),
            api=api.virtualization.virtual_machines
        )
        result.extend(pairs)

    return result


def sync_disks(api: NetboxAPI, vm_pair_list: List[Tuple[NetboxVM, ProxmoxVM]]):
    for netbox_vm, proxmox_vm in vm_pair_list:
        netbox_disks: Iterable[NetboxRecord] = api.virtualization.virtual_disks.filter(virtual_machine_id=netbox_vm.id)
        upsert_pairs(
            netbox_entities=netbox_disks,
            proxmox_entities=proxmox_vm.disks,
            match_function=lambda x, y: x.name == y.id,
            netbox_data_function=lambda y: prepare_disk_data(netbox_vm, y),
            api=api.virtualization.virtual_disks
        )


def sync_interfaces(api: NetboxAPI, vm_pair_list: List[Tuple[NetboxVM, ProxmoxVM]]):
    for netbox_vm, proxmox_vm in vm_pair_list:
        netbox_interfaces: Iterable[NetboxRecord] = api.virtualization.interfaces.filter(virtual_machine_id=netbox_vm.id)
        interface_pairs = upsert_pairs(
            netbox_entities=netbox_interfaces,
            proxmox_entities=proxmox_vm.interfaces,
            match_function=lambda x, y: x.name == y.name,
            netbox_data_function=lambda y: prepare_interface_data(netbox_vm, y),
            api=api.virtualization.interfaces
        )

        for netbox_interface, proxmox_interface in interface_pairs:
            all_proxmox_ips = proxmox_interface.ipv4_addresses + proxmox_interface.ipv6_addresses
            netbox_ips: NetboxRecordSet = api.ipam.ip_addresses.filter(address=all_proxmox_ips)
            upsert_pairs(
                netbox_entities=netbox_ips,
                proxmox_entities=all_proxmox_ips,
                match_function=lambda x, y: x.address == y,
                netbox_data_function=lambda y: prepare_ip_data(netbox_interface, y),
                api=api.ipam.ip_addresses
            )