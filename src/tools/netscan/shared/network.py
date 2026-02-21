from __future__ import annotations

import ipaddress
import re
import shutil
import subprocess

from buvis.pybase.result import FatalError

NMAP_REPORT_PATTERN = re.compile(r"Nmap scan report for (?:(\S+) \((\d+\.\d+\.\d+\.\d+)\)|(\d+\.\d+\.\d+\.\d+))")


def get_subnet(interface: str) -> str:
    try:
        result = subprocess.run(
            ["ifconfig", interface],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise FatalError("ifconfig not found. Install: apt install net-tools (Linux)")
    if result.returncode != 0:
        raise FatalError(f"Interface {interface} not found")

    pattern = re.compile(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b.*?\bnetmask\s+(\S+)")
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if not match:
            continue

        addr, mask = match.groups()
        if mask.startswith("0x"):
            mask = str(ipaddress.IPv4Address(int(mask, 16)))

        return str(ipaddress.IPv4Network(f"{addr}/{mask}", strict=False))

    raise FatalError(f"No IPv4 address on interface {interface}")


def validate_nmap() -> str:
    nmap_path = shutil.which("nmap")
    if nmap_path is None:
        raise FatalError("nmap not found. Install: brew install nmap (macOS) or apt install nmap (Linux)")
    return nmap_path
