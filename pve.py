import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import *

from proxmoxer import ProxmoxAPI, ProxmoxResource, ResourceException

from models.pve import ProxmoxVM, PveDisk, PveInterface, OSInfo


def _get_node_disks(pve: ProxmoxAPI, node: str) -> List[PveDisk]:
    result = []
    storages = pve.nodes(node).storage.get()
    storages = filter(lambda x: 'images' in x['content'], storages)
    storages = map(lambda x: x['storage'], storages)
    for storage in storages:
        disks = pve.nodes(node).storage(storage).content.get()
        disks = filter(lambda x: 'vmid' in x, disks)
        for disk in disks:
            identifier, vmid, size = disk['volid'], disk['vmid'], disk['size']
            result.append(PveDisk(identifier, vmid, size))
    return result


def _vm_execute_agent_command(api: ProxmoxResource, command: List[str], timeout_ms=1000) -> str | None:
    try:
        pid = api.agent('exec').create(command=command)['pid']
    # guest-exec is not allowed most likely
    except ResourceException:
        return None

    start_time = datetime.now()
    while (datetime.now() - start_time) < timedelta(milliseconds=timeout_ms):
        status = api.agent('exec-status').get(pid=pid)
        if status['exited'] == 1:
            if status.get('exitcode') == 0:
                try:
                    return status['out-data']
                except AttributeError:
                    return None
            else:
                return None
    return None


def _get_vm_primary_ip(api: ProxmoxResource, ipv4: bool) -> str | None:
    addr = '8.8.8.8' if ipv4 else '2001:4860:4860::8888'
    command = ['/sbin/ip', '-json', 'route', 'get', addr]
    src = _vm_execute_agent_command(api, command)
    src = json.loads(src or '[{}]')[0]
    return src.get('prefsrc', None)


def _get_vm_interfaces(api: ProxmoxResource) -> List[PveInterface]:
    result = []
    interfaces_blacklist = ['docker', 'veth.*', 'vnet.*', 'virbr.*', 'br-.*', 'usb.*', 'lo']
    command = ['/sbin/ip', '-json', 'addr']
    interfaces = _vm_execute_agent_command(api, command)
    interfaces = json.loads(interfaces or '{}')
    interfaces = filter(lambda x: all([not re.match(i, x.get('ifname', '')) for i in interfaces_blacklist]), interfaces)
    for interface_details in interfaces:
        name = interface_details['ifname']
        mtu = interface_details['mtu']
        mac = interface_details.get('address')
        # Remove link-local addresses
        addresses = filter(lambda x: x.get('scope', '') != 'local', interface_details.get('addr_info', []))
        ipv4 = filter(lambda x: x['family'] == 'inet', addresses)
        ipv4 = list(map(lambda x: f'{x['local']}/{x['prefixlen']}', ipv4))
        ipv6 = filter(lambda x: x['family'] == 'inet6', addresses)
        ipv6 = list(map(lambda x: f'{x['local']}/{x['prefixlen']}', ipv6))
        interface = PveInterface(name, ipv4, ipv6, mtu, mac)
        result.append(interface)
    return result


def _get_node_osinfo(pve: ProxmoxAPI) -> OSInfo | None:
    try:
        os_info = pve.agent('get-osinfo').get().get('result', {})
    except ResourceException:
        return None
    os_id = os_info.get('id', None)
    pretty = os_info.get('pretty-name', None)
    name = os_info.get('name', None)
    version = os_info.get('version', None)
    version_id = os_info.get('version-id', None)
    return OSInfo(os_id, pretty, name, version, version_id)


def _process_single_summary(api: ProxmoxAPI, node: str, all_disks: List[PveDisk], summary: dict) -> ProxmoxVM:
    vmid = summary['vmid']
    api = api.nodes(node).qemu(vmid)
    config = api.config.get()
    disks = list(filter(lambda x: x.vmid == vmid, all_disks))
    ipv4 = _get_vm_primary_ip(api, ipv4=True)
    ipv6 = _get_vm_primary_ip(api, ipv4=False)
    interfaces = _get_vm_interfaces(api)
    osinfo = _get_node_osinfo(api)
    name = summary['name']
    vm = ProxmoxVM(
        node=node,
        summary=summary,
        config=config,
        ipv4=ipv4,
        ipv6=ipv6,
        disks=disks,
        osinfo=osinfo,
        name=name,
        interfaces=interfaces,
    )
    return vm


def _get_node_vms(api: ProxmoxAPI, node: str, all_disks: List[PveDisk]) -> List[ProxmoxVM]:
    vm_summaries = api.nodes(node).qemu.get()

    def _process_wrapper(summary: dict) -> ProxmoxVM:
        return _process_single_summary(api, node, all_disks, summary)

    with ThreadPoolExecutor() as executor:
        result = list(executor.map(_process_wrapper, vm_summaries))
    return result


def proxmox_nodes(api: ProxmoxAPI) -> List[str]:
    nodes = api.nodes().get()
    return list(map(lambda x: x['node'], nodes))


def proxmox_vms(api: ProxmoxAPI) -> list[ProxmoxVM]:
    result = []
    nodes = api.nodes().get()

    for node_summary in nodes:
        node = node_summary['node']
        disks = _get_node_disks(api, node)
        vms = _get_node_vms(api, node, disks)
        result.extend(vms)

    return result


if __name__ == '__main__':
    import utils.common
    _api = utils.common.get_proxmox_api()
    inventory = sorted(proxmox_vms(_api), key=lambda x: x.vmid)
    list(map(print, inventory))
