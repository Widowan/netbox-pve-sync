from typing import List


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
        self.disks: List[PveDisk] = disks
        self.osinfo = osinfo
        self.name = name
        self.interfaces = interfaces

    def __str__(self):
        disks = ';'.join(map(str, self.disks))
        ram = int(self.ram / 1024 / 1024)
        interfaces = ';'.join(map(str, self.interfaces))
        return f'id={self.name}:{self.vmid}@{self.node},cpu={self.cpu},ram={ram}M,ipv4={self.ipv4},genid={self.uuid},disks=[{disks}],ifaces=[{interfaces}]'


class PveDisk:
    def __init__(self, identifier: str, vmid: int, size: int):
        self.id = identifier
        self.vmid = vmid
        self.storage, self.name = self.id.split(':', 1)
        self.size = size

    def __str__(self):
        size = int(self.size / 1024 / 1024)
        return f'id={self.id}@{self.vmid}:size={size}M'


class PveInterface:
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
