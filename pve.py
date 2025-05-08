import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import *

from proxmoxer import ProxmoxAPI, ProxmoxResource, ResourceException

PVE_HOST = os.environ["PVE_HOST"]
PVE_PORT = os.environ["PVE_PORT"]
PVE_USER = os.environ["PVE_USER"]
PVE_TOKEN_NAME = os.environ["PVE_TOKEN_NAME"]
PVE_TOKEN_VALUE = os.environ["PVE_TOKEN_VALUE"]
PVE_VERIFY_SSL = bool(os.environ.get("PVE_VERIFY_SSL", "false"))


def __get_proxmox_api():
    return ProxmoxAPI(
        PVE_HOST,
        port=PVE_PORT,
        user=PVE_USER,
        token_name=PVE_TOKEN_NAME,
        token_value=PVE_TOKEN_VALUE,
        verify_ssl=PVE_VERIFY_SSL,
    )


class ProxmoxVM:
    def __init__(self, node, summary, config, disks, ipv4, ipv6, osinfo, name, interfaces):
        self.node = node
        self.vmid = summary['vmid']
        self.cpu = summary['cpus']
        self.ram = summary['maxmem']
        self.tags = map(lambda x: x.strip(), config.get('tags', []))
        self.tags = list(filter(lambda x: x, self.tags))
        self.uuid = config.get('vmgenid', None)
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.disks: List[Disk] = disks
        self.osinfo = osinfo
        self.name = name
        self.interfaces = interfaces

    def __str__(self):
        disks = ';'.join(map(str, self.disks))
        ram = int(self.ram / 1024 / 1024)
        interfaces = ';'.join(map(str, self.interfaces))
        return f'id={self.name}:{self.vmid}@{self.node},cpu={self.cpu},ram={ram}M,ipv4={self.ipv4},genid={self.uuid},disks=[{disks}],ifaces=[{interfaces}]'


class Disk:
    def __init__(self, identifier: str, vmid: int, size: int):
        self.id = identifier
        self.vmid = vmid
        self.storage, self.name = self.id.split(':', 1)
        self.size = size

    def __str__(self):
        size = int(self.size / 1024 / 1024)
        return f'id={self.id}@{self.vmid}:size={size}M'


def _get_node_disks(pve: ProxmoxAPI, node: str) -> List[Disk]:
    result = []
    storages = pve.nodes(node).storage.get()
    storages = filter(lambda x: 'images' in x['content'], storages)
    storages = map(lambda x: x['storage'], storages)
    for storage in storages:
        disks = pve.nodes(node).storage(storage).content.get()
        disks = filter(lambda x: 'vmid' in x, disks)
        for disk in disks:
            identifier, vmid, size = disk['volid'], disk['vmid'], disk['size']
            result.append(Disk(identifier, vmid, size))
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


class Interface:
    def __init__(self, name, ipv4_addresses, ipv6_addresses, mtu, mac):
        self.name = name
        self.ipv4_addresses = ipv4_addresses
        self.ipv6_addresses = ipv6_addresses
        self.mtu = mtu
        self.mac = mac

    def __str__(self):
        ipv4 = ','.join(self.ipv4_addresses)
        ipv6 = ','.join(self.ipv6_addresses)
        return f'name={self.name};mtu={self.mtu};ipv4={ipv4};ipv6={ipv6}'


class OSInfo:
    def __init__(self, os_id, pretty, name, version, version_id):
        self.id = os_id,
        self.pretty = pretty
        self.name = name
        self.version = version
        self.version_id = version_id

    def __str__(self):
        return f'{self.pretty}' or f'{self.name} {self.version or self.version_id}'


def _get_vm_interfaces(api: ProxmoxResource) -> List[Interface]:
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
        interface = Interface(name, ipv4, ipv6, mtu, mac)
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


def _process_single_summary(api: ProxmoxAPI, node: str, all_disks: List[Disk], summary: dict) -> ProxmoxVM:
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


def _get_node_vms(api: ProxmoxAPI, node: str, all_disks: List[Disk]) -> List[ProxmoxVM]:
    vm_summaries = api.nodes(node).qemu.get()

    def _process_wrapper(summary: dict) -> ProxmoxVM:
        return _process_single_summary(api, node, all_disks, summary)

    with ThreadPoolExecutor() as executor:
        result = list(executor.map(_process_wrapper, vm_summaries))
    return result


def proxmox_nodes() -> List[str]:
    pve = __get_proxmox_api()
    nodes = pve.nodes().get()
    return list(map(lambda x: x['node'], nodes))


def proxmox_vms() -> list[ProxmoxVM]:
    result = []
    pve = __get_proxmox_api()
    nodes = pve.nodes().get()

    for node_summary in nodes:
        node = node_summary['node']
        disks = _get_node_disks(pve, node)
        vms = _get_node_vms(pve, node, disks)
        result.extend(vms)

    return result


if __name__ == '__main__':
    inventory = sorted(proxmox_vms(), key=lambda x: x.vmid)
    list(map(print, inventory))
