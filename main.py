import netbox
import pve
import utils.netbox
import utils.proxmox


def main():
    netbox_api = utils.netbox.get_netbox_api()
    proxmox_api = utils.proxmox.get_proxmox_api()
    proxmox_nodes = pve.collect_nodes(proxmox_api)
    proxmox_vms = pve.collect_vms(proxmox_api, proxmox_nodes)

    vm_pairs = netbox.sync_vms(netbox_api, proxmox_vms, proxmox_nodes)
    netbox.sync_disks(netbox_api, vm_pairs)
    netbox.sync_interfaces(netbox_api, vm_pairs)


if __name__ == '__main__':
    main()
