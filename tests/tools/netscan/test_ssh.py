from __future__ import annotations

import subprocess

from netscan.commands.ssh.ssh import CommandSsh

NMAP_SSH_OUTPUT = """Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for router.local (192.168.1.1)
Host is up (0.0050s latency).
PORT   STATE SERVICE
22/tcp open  ssh

Nmap scan report for 192.168.1.50
Host is up (0.0010s latency).
PORT   STATE SERVICE
22/tcp open  ssh

Nmap done: 256 IP addresses (2 hosts up) scanned in 5.10 seconds
"""

NMAP_SSH_NONE = """Starting Nmap 7.94 ( https://nmap.org )
Nmap done: 256 IP addresses (0 hosts up) scanned in 5.10 seconds
"""


class TestCommandSsh:
    def test_finds_ssh_hosts_sorted(self, mocker) -> None:
        mocker.patch("netscan.commands.ssh.ssh.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.ssh.ssh.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.ssh.ssh.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=NMAP_SSH_OUTPUT, stderr=""),
        )

        result = CommandSsh(interface="en0", port=22).execute()

        assert result.success is True
        lines = result.output.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("192.168.1.1\t")
        assert lines[1] == "192.168.1.50"

    def test_no_ssh_hosts(self, mocker) -> None:
        mocker.patch("netscan.commands.ssh.ssh.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.ssh.ssh.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.ssh.ssh.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=NMAP_SSH_NONE, stderr=""),
        )

        result = CommandSsh(interface="en0", port=22).execute()
        assert result.success is True
        assert "No hosts with open port 22" in result.output

    def test_nmap_failure(self, mocker) -> None:
        mocker.patch("netscan.commands.ssh.ssh.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.ssh.ssh.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.ssh.ssh.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="nmap: error"),
        )

        result = CommandSsh(interface="en0", port=22).execute()
        assert result.success is False
        assert "error" in result.error

    def test_custom_port(self, mocker) -> None:
        mocker.patch("netscan.commands.ssh.ssh.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.ssh.ssh.get_subnet", return_value="10.0.0.0/24")
        run_mock = mocker.patch(
            "netscan.commands.ssh.ssh.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=NMAP_SSH_NONE, stderr=""),
        )

        CommandSsh(interface="eth0", port=2222).execute()
        call_args = run_mock.call_args[0][0]
        assert "-p" in call_args
        assert "2222" in call_args
