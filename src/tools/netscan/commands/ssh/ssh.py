from __future__ import annotations

import ipaddress
import re
import subprocess

from buvis.pybase.result import CommandResult

from netscan.shared.network import NMAP_REPORT_PATTERN, get_subnet, validate_nmap


class CommandSsh:
    def __init__(self: CommandSsh, interface: str, port: int) -> None:
        self.interface = interface
        self.port = port

    def execute(self: CommandSsh) -> CommandResult:
        nmap_path = validate_nmap()
        subnet = get_subnet(self.interface)

        result = subprocess.run(
            [nmap_path, "-p", str(self.port), "--open", subnet],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return CommandResult(success=False, error=f"nmap scan failed: {result.stderr.strip()}")

        open_port_pattern = re.compile(rf"{self.port}/tcp\s+open\b")

        hosts: list[tuple[str, str | None]] = []
        current_ip: str | None = None
        current_hostname: str | None = None
        current_open = False

        for line in result.stdout.splitlines():
            match = NMAP_REPORT_PATTERN.search(line)
            if match:
                if current_ip is not None and current_open:
                    hosts.append((current_ip, current_hostname))
                if match.group(3):
                    current_ip = match.group(3)
                    current_hostname = None
                else:
                    current_hostname = match.group(1)
                    current_ip = match.group(2)
                current_open = False
                continue

            if current_ip is not None and open_port_pattern.search(line):
                current_open = True

        if current_ip is not None and current_open:
            hosts.append((current_ip, current_hostname))

        if not hosts:
            return CommandResult(success=True, output=f"No hosts with open port {self.port} found")

        hosts.sort(key=lambda host: ipaddress.IPv4Address(host[0]))
        output = "\n".join(f"{ip}\t{hostname}" if hostname else ip for ip, hostname in hosts)
        return CommandResult(success=True, output=output)
