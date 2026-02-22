from __future__ import annotations

import subprocess

from netscan.commands.hosts.hosts import CommandHosts

NMAP_SN_OUTPUT = """Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for router.local (192.168.1.1)
Host is up (0.0050s latency).
Nmap scan report for 192.168.1.100
Host is up (0.0010s latency).
Nmap scan report for mypc.local (192.168.1.50)
Host is up (0.0020s latency).
Nmap done: 256 IP addresses (3 hosts up) scanned in 2.05 seconds
"""


class TestCommandHosts:
    def test_lists_hosts_sorted_by_ip(self, mocker) -> None:
        mocker.patch("netscan.commands.hosts.hosts.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.hosts.hosts.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.hosts.hosts.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=NMAP_SN_OUTPUT, stderr=""),
        )

        result = CommandHosts(interface="en0").execute()

        assert result.success is True
        lines = result.output.splitlines()
        assert len(lines) == 3
        assert lines[0].startswith("192.168.1.1\t")
        assert "192.168.1.50" in lines[1]
        assert lines[2] == "192.168.1.100"

    def test_empty_scan(self, mocker) -> None:
        mocker.patch("netscan.commands.hosts.hosts.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.hosts.hosts.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.hosts.hosts.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Starting Nmap 7.94\nNmap done: 256 IP addresses (0 hosts up)\n",
                stderr="",
            ),
        )

        result = CommandHosts(interface="en0").execute()
        assert result.success is True
        assert result.output == ""

    def test_nmap_failure(self, mocker) -> None:
        mocker.patch("netscan.commands.hosts.hosts.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.hosts.hosts.get_subnet", return_value="192.168.1.0/24")
        mocker.patch(
            "netscan.commands.hosts.hosts.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="nmap: permission denied"
            ),
        )

        result = CommandHosts(interface="en0").execute()
        assert result.success is False
        assert "permission denied" in result.error

    def test_regex_match_with_no_ip(self, mocker) -> None:
        """Covers ip_text is None branch (line 35-36)."""
        mocker.patch("netscan.commands.hosts.hosts.validate_nmap", return_value="/usr/local/bin/nmap")
        mocker.patch("netscan.commands.hosts.hosts.get_subnet", return_value="192.168.1.0/24")

        # Craft output where NMAP_REPORT_PATTERN matches but both ip groups are None
        # This can't normally happen with the regex, but we mock the pattern to test the guard
        from unittest.mock import MagicMock

        fake_match = MagicMock()
        fake_match.groups.return_value = ("hostname", None, None)

        original_pattern = mocker.patch("netscan.commands.hosts.hosts.NMAP_REPORT_PATTERN")
        original_pattern.search.side_effect = [fake_match, None]  # one match then done

        mocker.patch(
            "netscan.commands.hosts.hosts.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Nmap scan report for hostname\n", stderr=""
            ),
        )

        result = CommandHosts(interface="en0").execute()
        assert result.success is True
        assert result.output == ""
