from datetime import datetime, timedelta
from typing import List

from proxmoxer import ProxmoxAPI, ProxmoxResource, ResourceException

import config


def get_proxmox_api():
    return ProxmoxAPI(
        config.PVE_HOST,
        port=config.PVE_PORT,
        user=config.PVE_USER,
        token_name=config.PVE_TOKEN_NAME,
        token_value=config.PVE_TOKEN_VALUE,
        verify_ssl=config.PVE_VERIFY_SSL,
    )


def execute_vm_agent_command(api: ProxmoxResource, command: List[str], timeout_ms=1000) -> str | None:
    try:
        pid = api.agent('exec').create(command=command)['pid']
    # guest-exec is not allowed most likely
    except ResourceException:
        return None

    start_time = datetime.now()
    while (datetime.now() - start_time) < timedelta(milliseconds=timeout_ms):
        status = api.agent('exec-status').get(pid=pid)
        if status['exited'] == 1:
            return status.get('out-data')
    return None
