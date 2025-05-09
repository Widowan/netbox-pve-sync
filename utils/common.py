from typing import Iterable, List, Tuple

import pynetbox
from proxmoxer import ProxmoxAPI
from pynetbox.core.api import Api as NetboxAPI

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


def full_outer_join(first: Iterable, second: Iterable, eq=lambda x, y: x == y) -> List[Tuple[object | None, object | None]]:
    result = []
    second_matches = {j: False for j in second}
    for i in first:
        first_matched = False
        for j in second:
            if eq(i, j):
                first_matched = True
                second_matches[j] = True
                result.append((i, j))
        if not first_matched:
            result.append((i, None))
    result.extend((None, k) for k, v in second_matches.items() if not v)
    return result


def get_netbox_api() -> NetboxAPI:
    return pynetbox.api(url=config.NB_HOST, token=config.NB_TOKEN)
