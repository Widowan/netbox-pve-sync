import netbox
import pve
import utils.common


def nb_main():
    netbox_api = utils.common.get_netbox_api()
    proxmox_api = utils.common.get_proxmox_api()
    pve_vms = pve.proxmox_vms(proxmox_api)
    pve_nodes = pve.proxmox_nodes(proxmox_api)
    vm_list = netbox.populate_vms(netbox_api, pve_vms, pve_nodes)
    netbox.populate_disks(netbox_api, vm_list)
    netbox.populate_interfaces(netbox_api, vm_list)


if __name__ == '__main__':
    nb_main()
