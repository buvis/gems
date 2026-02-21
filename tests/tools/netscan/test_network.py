from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError
from netscan.shared.network import get_subnet, validate_nmap


class TestGetSubnet:
    def test_parses_macos_ifconfig(self, mocker) -> None:
        mocker.patch(
            "netscan.shared.network.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["ifconfig", "en0"],
                returncode=0,
                stdout="inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255\n",
                stderr="",
            ),
        )
        assert get_subnet("en0") == "192.168.1.0/24"

    def test_parses_linux_ifconfig(self, mocker) -> None:
        mocker.patch(
            "netscan.shared.network.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["ifconfig", "eth0"],
                returncode=0,
                stdout="inet 10.0.0.5  netmask 255.255.255.0  broadcast 10.0.0.255\n",
                stderr="",
            ),
        )
        assert get_subnet("eth0") == "10.0.0.0/24"

    def test_interface_not_found(self, mocker) -> None:
        mocker.patch(
            "netscan.shared.network.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["ifconfig", "bad0"],
                returncode=1,
                stdout="",
                stderr="ifconfig: interface bad0 does not exist",
            ),
        )
        with pytest.raises(FatalError, match="not found"):
            get_subnet("bad0")

    def test_ifconfig_not_installed(self, mocker) -> None:
        mocker.patch(
            "netscan.shared.network.subprocess.run",
            side_effect=FileNotFoundError,
        )
        with pytest.raises(FatalError, match="ifconfig not found"):
            get_subnet("en0")

    def test_no_ipv4_address(self, mocker) -> None:
        mocker.patch(
            "netscan.shared.network.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["ifconfig", "en0"],
                returncode=0,
                stdout="inet6 fe80::1%en0 prefixlen 64 scopeid 0x1\n",
                stderr="",
            ),
        )
        with pytest.raises(FatalError, match="No IPv4"):
            get_subnet("en0")


class TestValidateNmap:
    def test_nmap_found(self, mocker) -> None:
        mocker.patch("netscan.shared.network.shutil.which", return_value="/usr/local/bin/nmap")
        assert validate_nmap() == "/usr/local/bin/nmap"

    def test_nmap_not_found(self, mocker) -> None:
        mocker.patch("netscan.shared.network.shutil.which", return_value=None)
        with pytest.raises(FatalError, match="nmap not found"):
            validate_nmap()
