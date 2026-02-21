from __future__ import annotations

import ipaddress
import subprocess

from buvis.pybase.result import CommandResult

from netscan.shared.network import NMAP_REPORT_PATTERN, get_subnet, validate_nmap


class CommandHosts:
    def __init__(self: CommandHosts, interface: str) -> None:
        self.interface = interface

    def execute(self: CommandHosts) -> CommandResult:
        nmap_path = validate_nmap()
        subnet = get_subnet(self.interface)

        result = subprocess.run(
            [nmap_path, "-sn", subnet],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return CommandResult(success=False, error=f"nmap scan failed: {result.stderr.strip()}")

        hosts: list[tuple[ipaddress.IPv4Address, str]] = []
        for line in result.stdout.splitlines():
            match = NMAP_REPORT_PATTERN.search(line)
            if not match:
                continue
            hostname, ip_with_host, ip_only = match.groups()
            ip_text = ip_with_host or ip_only
            if ip_text is None:
                continue
            hosts.append((ipaddress.IPv4Address(ip_text), hostname or ""))

        hosts.sort(key=lambda item: item[0])
        output = "\n".join(f"{ip}\t{hostname}" if hostname else f"{ip}" for ip, hostname in hosts)
        return CommandResult(success=True, output=output)
