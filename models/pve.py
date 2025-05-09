import json
import re
from datetime import datetime, timedelta
from typing import List, Any

from proxmoxer import ProxmoxResource, ResourceException

from config import INTERFACES_BLACKLIST


INTERFACES_COMMAND = ['/sbin/ip', '-json', 'addr']
IP_TEMPLATE = "{}/{}"


class PveDisk:
    def __init__(self, *, identifier: str, vmid: int, size: int):
        self.id = identifier
        self.vmid = vmid
        self.size = size

    def __str__(self):
        size = int(self.size / 1024 / 1024)
        return f'id={self.id}@{self.vmid}:size={size}M'


class PveInterface:
    def __init__(
            self, *,
            name: str,
            mtu: int | None = None,
            mac: str | None = None,
            ipv4_addresses: List[str] = None,
            ipv6_addresses: List[str] = None,
            state: bool = True
    ):
        self.name: str = name
        self.mtu: int | None = mtu
        self.mac: str | None = mac
        self.ipv4_addresses: List[str] = ipv4_addresses or []
        self.ipv6_addresses: List[str] = ipv6_addresses or []
        self.state = state

    def __str__(self):
        ipv4 = ','.join(self.ipv4_addresses)
        ipv6 = ','.join(self.ipv6_addresses)
        state = 'Up' if self.state else 'Down'
        return f'name={self.name};state={state};mtu={self.mtu};ipv4={ipv4};ipv6={ipv6}'


class OSInfo:
    def __init__(
            self,
            os_id:       str | None = None,
            version_id:  str | None = None,
            pretty_name: str | None = None,
    ):
        self.id          = os_id,
        self.pretty_name = pretty_name
        self.version_id  = version_id

    def __str__(self):
        return f'{self.pretty_name}' or f'{self.id} {self.version_id}'


class ProxmoxVM:
    def __init__(self, summary: dict, config: dict, api: ProxmoxResource | None = None):
        self.name: str = summary['name']
        self.vmid: int = summary['vmid']
        self.cpu:  int = summary['cpus']
        self.ram:  int = summary['maxmem']
        self.uuid: str = config['vmgenid']

        self.api: ProxmoxResource = api.qemu(self.vmid)

        self.node: str | None = None
        self.ipv4: str | None = None
        self.ipv6: str | None = None

        self.os: OSInfo | None = None

        self.disks:      List[PveDisk]      = []
        self.interfaces: List[PveInterface] = []

    def attach_node(self, node: str):
        self.node = node


    def attach_relevant_disks(self, all_disks: List[PveDisk]):
        for disk in all_disks:
            if disk.vmid == self.vmid:
                if not any(filter(lambda x: x.id == disk.id, self.disks)):
                    self.disks.append(disk)

    def _execute_agent_command(self, command: List[str], timeout_ms: int = 1000) -> str | None:
        try:
            pid = self.api.agent('exec').create(command=command)['pid']
        # guest-exec is not allowed most likely
        except ResourceException:
            return None

        start_time = datetime.now()
        while (datetime.now() - start_time) < timedelta(milliseconds=timeout_ms):
            status: dict[str, Any] = self.api.agent('exec-status').get(pid=pid)
            if status.get('exited') == 1:
                return status.get('out-data')
        return None

    def attach_interfaces(self):
        interfaces = self._execute_agent_command(INTERFACES_COMMAND) or '[]'
        interfaces = json.loads(interfaces)

        for interface in interfaces:
            name = interface.get('ifname')
            blacklist_hits = [re.fullmatch(pattern, name) for pattern in INTERFACES_BLACKLIST]
            if not any(blacklist_hits):
                state = interface.get('operstate') == 'UP'
                mac_address = interface.get('address')
                mtu = interface.get('mtu')
                ipv4_addresses = []
                ipv6_addresses = []
                for address in interface.get('addr_info'):
                    # Remove link-local addresses
                    if address.get('scope') != 'local' and address.get('local') and address.get('prefixlen'):
                        ip = IP_TEMPLATE.format(address['local'], address['prefixlen'])
                        if address.get('family') == 'inet':
                            ipv4_addresses.append(ip)
                        elif address.get('family') == 'inet6':
                            ipv4_addresses.append(ip)

                interface = PveInterface(
                    name=name,
                    mac=mac_address,
                    mtu=mtu,
                    ipv4_addresses=ipv4_addresses,
                    ipv6_addresses=ipv6_addresses,
                    state=state
                )

                self.interfaces.append(interface)

    def attach_os_info(self):
        try:
            os_release = self.api.agent('get-osinfo').get().get('result', {})
            # os-release(5) recommends LIKE= as a fallback, but QGA doesn't expose that
            os_id = os_release.get('id')
            os_version_id = os_release.get('version-id')
            os_pretty_name = os_release.get('pretty-name')
            self.os = OSInfo(
                os_id=os_id,
                version_id=os_version_id,
                pretty_name=os_pretty_name
            )
        except ResourceException:
            self.os = None
            return

    def __str__(self):
        disks = ';'.join(map(str, self.disks))
        ram = int(self.ram / 1024 / 1024)
        interfaces = ';'.join(map(str, self.interfaces))
        return f'id={self.name}:{self.vmid}@{self.node},cpu={self.cpu},ram={ram}M,ipv4={self.ipv4},genid={self.uuid},disks=[{disks}],ifaces=[{interfaces}]'
