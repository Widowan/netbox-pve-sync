import os

NETBOX_HOST = os.environ["NETBOX_HOST"]
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
HYPERVISOR_DEVICE_TYPE = os.environ.get("HYPERVISOR_DEVICE_TYPE", "proxmox-ve")
EXTERNAL_FIELD_SLUG = os.environ.get("EXTERNAL_FIELD_SLUG", "external")
DISK_SIZE_UNIT = 1000

PVE_HOST = os.environ["PVE_HOST"]
PVE_PORT = os.environ["PVE_PORT"]
PVE_USER = os.environ["PVE_USER"]
PVE_TOKEN_NAME = os.environ["PVE_TOKEN_NAME"]
PVE_TOKEN_VALUE = os.environ["PVE_TOKEN_VALUE"]
PVE_VERIFY_SSL = bool(os.environ.get("PVE_VERIFY_SSL", "false"))

INTERFACES_BLACKLIST = ['docker.*', 'veth.*', 'vnet.*', 'virbr.*', 'br-.*', 'usb.*', 'lo']