from concurrent.futures import ThreadPoolExecutor
from typing import List

from proxmoxer import ProxmoxAPI, ProxmoxResource

import utils.proxmox
from models.pve import PveDisk, ProxmoxVM


def _collect_node_disks(api: ProxmoxResource) -> List[PveDisk]:
    result = []

    storages = api.storage.get()
    storages = filter(lambda x: 'images' in x.get('content', ''), storages)
    storages = map(lambda x: x.get('storage'), storages)

    for storage in storages:
        disks = api.storage(storage).content.get()
        disks = filter(lambda x: 'vmid' in x, disks)
        for disk in disks:
            identifier, vmid, size = disk['volid'], disk['vmid'], disk['size']
            disk = PveDisk(
                identifier=identifier,
                vmid=vmid,
                size=size
            )
            result.append(disk)
    return result

def _collect_node_vms(api: ProxmoxResource) -> List[ProxmoxVM]:
    result = []
    vm_summaries = api.qemu.get()

    for summary in vm_summaries:
        config = api.qemu(summary['vmid']).config.get()
        vm = ProxmoxVM(
            summary=summary,
            config=config,
            api=api
        )
        result.append(vm)

    return result


def collect_vms(api: ProxmoxAPI, nodes: str | List[str]):
    result = []
    if type(nodes) == str:
        nodes = [nodes]

    all_disks: List[PveDisk] = []
    for node in nodes:
        all_disks.extend(_collect_node_disks(api.nodes(node)))

    def process_vm(vm, _node):
        vm.attach_node(_node)
        vm.attach_relevant_disks(all_disks)
        vm.attach_interfaces()
        vm.attach_os_info()

    for node in nodes:
        vms = _collect_node_vms(api.nodes(node))
        with ThreadPoolExecutor() as executor:
            executor.map(lambda vm: process_vm(vm, node), vms)
        result.extend(vms)

    return result

def collect_nodes(api: ProxmoxAPI) -> List[str]:
    nodes = api.nodes().get()
    return [i['node'] for i in nodes]

if __name__ == '__main__':
    import utils.common
    _api = utils.proxmox.get_proxmox_api()
    _nodes = collect_nodes(_api)
    inventory = sorted(collect_vms(_api, _nodes), key=lambda x: x.vmid)
    list(map(print, inventory))
