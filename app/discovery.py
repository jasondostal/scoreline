"""
WLED device discovery via mDNS.

WLED devices advertise themselves as _wled._tcp.local.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser


@dataclass
class WLEDDevice:
    """Discovered WLED device."""
    name: str
    host: str
    ip: str
    port: int
    mac: Optional[str] = None


class WLEDDiscoveryListener(ServiceListener):
    """Listener for WLED service discovery."""

    def __init__(self):
        self.devices: dict[str, WLEDDevice] = {}

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Called when a service is discovered."""
        info = zc.get_service_info(service_type, name)
        if info:
            self._add_device(name, info)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Called when a service is updated."""
        info = zc.get_service_info(service_type, name)
        if info:
            self._add_device(name, info)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        """Called when a service is removed."""
        # Clean up the name to match our key
        clean_name = name.replace("._wled._tcp.local.", "")
        if clean_name in self.devices:
            del self.devices[clean_name]

    def _add_device(self, name: str, info) -> None:
        """Add or update a device from service info."""
        # Extract IP address
        if info.addresses:
            ip = ".".join(str(b) for b in info.addresses[0])
        else:
            return  # No IP, skip

        # Clean up the service name
        clean_name = name.replace("._wled._tcp.local.", "")

        # Get MAC from properties if available
        mac = None
        if info.properties:
            mac = info.properties.get(b"mac", b"").decode("utf-8", errors="ignore")

        self.devices[clean_name] = WLEDDevice(
            name=clean_name,
            host=info.server.rstrip(".") if info.server else ip,
            ip=ip,
            port=info.port or 80,
            mac=mac or None,
        )


async def discover_wled_devices(timeout: float = 3.0) -> list[WLEDDevice]:
    """
    Discover WLED devices on the local network.

    Args:
        timeout: How long to scan for devices (seconds)

    Returns:
        List of discovered WLED devices
    """
    listener = WLEDDiscoveryListener()

    async with AsyncZeroconf() as azc:
        browser = AsyncServiceBrowser(
            azc.zeroconf,
            "_wled._tcp.local.",
            listener,
        )

        # Wait for discovery
        await asyncio.sleep(timeout)

        # Clean up
        await browser.async_cancel()

    return list(listener.devices.values())


def discover_wled_devices_sync(timeout: float = 3.0) -> list[WLEDDevice]:
    """
    Synchronous version of discover_wled_devices.

    Useful for testing or non-async contexts.
    """
    return asyncio.run(discover_wled_devices(timeout))


if __name__ == "__main__":
    # Quick test
    print("Scanning for WLED devices...")
    devices = discover_wled_devices_sync(timeout=5.0)

    if devices:
        print(f"\nFound {len(devices)} device(s):\n")
        for d in devices:
            print(f"  {d.name}")
            print(f"    IP: {d.ip}")
            print(f"    Host: {d.host}")
            print(f"    MAC: {d.mac or 'unknown'}")
            print()
    else:
        print("No WLED devices found.")
