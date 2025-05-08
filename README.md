### Personal project for syncing VMs from Proxmox to Netbox

---

This script will sync VMs from all of your proxmox nodes to Netbox.

#### Synced information:

- VM name
- CPU & RAM
- All virtual disks attached to it (i.e. `vm-115-disk-0`, `vm-115-disk-cloudinit`)
- All interfaces (except blacklisted patterns) and their primary IPs

#### Todo:

- Platforms (OS Version)

#### Requirements:

- Pre-existing physical devices for all PVE nodes (with same name) in Netbox <ins>**with type `proxmox-ve`**</ins> (type name configurable)
- Pre-existing virtual cluster in Netbox which the above node(s) are joined at (all nodes don't have to be in the same cluster)
- Guest VMs should include functioning qemu-guest-agent <ins>**with exec and exec-status commands enabled (it's used for IP information)**</ins>
- iptools2 on guest OS with json support (you should be fine unless you run ancient OS version like CentOS 7)
- Python3.10 (I think) or higher **on the OS running this script**
- Users for API in both Netbox and Proxmox

#### Rationale about qemu guest agent:

It is impossible to reliably extract primary IP address from a machine with just interfaces (`guest-network-get-interfaces` command on QGA).
Same goes for the routing table, but we cannot obtain it anyways as the QGA's `guest-network-get-route` command is unsupported as of writing.
So, instead of trying to parse it manually (and failing miserably), I decided to just ask kernel what's the primary IP is:
it's obtained via `ip route get 8.8.8.8` command (with ipv6 equivalent), hence why you need to have `exec` and `exec-status` command enabled in QGA settings.

#### Usage

1. Install the requirements:
    ```shell
    python3 -m venv venv
    ./venv/bin/pip3 install -r requirements.txt
    ```
2. Set up environment variables in any way you like (like .env file)
    ```dotenv
    # Note lack of https prefix. You *must* have HTTPS
    PVE_HOST="myproxmox.example.com"
    PVE_VERIFY_SSL=false
    PVE_PORT=8006
    # Create a user in Proxmox, if unsure just give it PVEAdmin role
    PVE_USER="netbox@pve"
    PVE_TOKEN_NAME="netbox"
    PVE_TOKEN_VALUE="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    NB_HOST="https://mynetbox.example.com"
    NB_TOKEN="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    HYPERVISOR_DEVICE_TYPE="proxmox-ve"
    ```
3. Run it in any way you like:
   ```shell
   ./venv/bin/python3 main.py
   ```
   Perhaps most useful would be either a cronjob:
   ```cron
   # /etc/cron.d/netbox_pve_sync
   */1 * * * * root source /opt/netbox-pve-sync/.env ; /opt/netbox-pve-sync/venv/bin/python3 /opt/netbox-pve-sync/main.py
   ```
   ...or a systemd unit & timer:
   ```systemd
   # /etc/systemd/system/netbox-pve-sync.service
   [Unit]
   Description=Synchronize Netbox with data from Proxmox VE
   After=network.target
   Wants=network-online.target

   [Service]
   Restart=always
   Type=simple
   EnvironmentFile=/opt/netbox-pve-sync/.env
   ExecStart=/opt/netbox-pve-sync/venv/bin/python3 /opt/netbox-pve-sync/main.py

   [Install]
   WantedBy=multi-user.target
   ```
   ```systemd
   # /etc/systemd/system/netbox-pve-sync.timer
   # Enable and start this timer instead of service file with
   # systemctl enable --now netbox-pve-sync.timer
   [Unit]
   Description=Timer for netbox-pve-sync.service

   [Timer]
   OnCalendar=minutely
   AccuracySec=1us
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```
   
-----
You may also use docker, but I felt that it'd be such a waste to package second python since the script is so small
