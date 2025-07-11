#!/usr/bin/env python3
"""
nRF Wi-Fi Provisioner CLI

A command-line tool for provisioning nRF 7002 devices to a Wi-Fi network,
mirroring the functionality of the Nordic Android nRF Wi-Fi Provisioner app.

Supports three provisioning modes:
- Bluetooth LE
- SoftAP (Wi-Fi)
- NFC (planned)

Usage:
        python3 nrf_wifi_provisioner_cli_fixed.py [OPTIONS] COMMAND [ARGS]...

Examples:
        # Discover and list available devices
        python3 nrf_wifi_provisioner_cli_fixed.py ble discover

        # Get device status via BLE
        python3 nrf_wifi_provisioner_cli_fixed.py ble status --device AA:BB:CC:DD:EE:FF

        # Scan for WiFi networks via BLE
        python3 nrf_wifi_provisioner_cli_fixed.py ble scan --device AA:BB:CC:DD:EE:FF

        # Configure WiFi via BLE
        python3 nrf_wifi_provisioner_cli_fixed.py ble configure --device AA:BB:CC:DD:EE:FF --ssid "MyWiFi" --password "mypassword"

        # Forget WiFi via BLE
        python3 nrf_wifi_provisioner_cli_fixed.py ble forget --device AA:BB:CC:DD:EE:FF

        # Use hybrid approach (bluetoothctl for pairing, Bleak for notifications)
        python3 nrf_wifi_provisioner_cli_fixed.py ble status --device AA:BB:CC:DD:EE:FF --hybrid
"""

import asyncio
import argparse
import sys
import json
import time
import subprocess
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from bleak import BleakScanner, BleakClient, BleakError

# Import the generated protobuf classes
try:
    import common_pb2
    import request_pb2
    import response_pb2
    import result_pb2
    import version_pb2
except ImportError:
    # Try importing from generated folder first, then current directory
    generated_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "generated"
    )
    if os.path.exists(generated_path):
        sys.path.insert(0, generated_path)

    # Also add current directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        import common_pb2
        import request_pb2
        import response_pb2
        import result_pb2
        import version_pb2
    except ImportError:
        print("Warning: Protobuf files not found. Some functionality may be limited.")
        print("Run 'make proto' to generate the required protobuf files.")
        print("Expected location: generated/ folder")

        # Create dummy classes for basic functionality
        class DummyProto:
            pass

        common_pb2 = DummyProto()
        request_pb2 = DummyProto()
        response_pb2 = DummyProto()
        result_pb2 = DummyProto()
        version_pb2 = DummyProto()


@dataclass
class WiFiNetwork:
    """Represents a discovered WiFi network"""

    ssid: str
    bssid: str
    channel: int
    auth_mode: str
    band: str
    rssi: Optional[int] = None


@dataclass
class DeviceStatus:
    """Represents device connection status"""

    state: str
    ssid: Optional[str] = None
    ip_address: Optional[str] = None
    bssid: Optional[str] = None
    channel: Optional[int] = None


class ProvisioningClient:
    """Base class for provisioning clients"""

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover available devices"""
        raise NotImplementedError

    async def get_status(
        self, device_id: str, use_hybrid: bool = False
    ) -> DeviceStatus:
        """Get device status"""
        raise NotImplementedError

    async def scan_networks(
        self, device_id: str, use_hybrid: bool = False
    ) -> List[WiFiNetwork]:
        """Scan for available WiFi networks"""
        raise NotImplementedError

    async def configure_wifi(
        self,
        device_id: str,
        ssid: str,
        password: str,
        auth_mode: str = "WPA2_PSK",
        volatile: bool = False,
        use_hybrid: bool = False,
    ) -> bool:
        """Configure WiFi settings"""
        raise NotImplementedError

    async def forget_config(self, device_id: str, use_hybrid: bool = False) -> bool:
        """Forget WiFi configuration"""
        raise NotImplementedError


class BLEProvisioningClient(ProvisioningClient):
    """Bluetooth LE provisioning client"""

    def __init__(self):
        self.control_point_char = None
        self.data_out_char = None
        self.info_char = None
        self.responses = []
        self.results = []
        self.client = None  # To hold the BleakClient instance

    def _disconnected_callback(self, client):
        """Synchronous callback for disconnection. Does not clear self.client."""
        print(f"[{time.strftime('%H:%M:%S')}] Device {client.address} disconnected!")
        # The main async functions (e.g., _ensure_connected_and_ready) are responsible
        # for handling the 'self.client' state based on connection status and errors.

    def bluetoothctl_pair_and_trust(self, address: str) -> bool:
        """Use bluetoothctl to pair and trust the device"""
        try:
            print(f"Using bluetoothctl to pair and trust device {address}...")

            # Attempt to remove device first to ensure a clean state
            remove_cmd = f"bluetoothctl remove {address}"
            subprocess.run(remove_cmd, shell=True, capture_output=True, text=True)
            time.sleep(1)

            bluetoothctl_commands = f"""
			power on
			agent on
			default-agent
			pair {address}
			trust {address}
			connect {address}
			quit
			"""

            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            print("Sending bluetoothctl commands:")
            for cmd in bluetoothctl_commands.strip().split("\n"):
                cmd = cmd.strip()
                if not cmd:
                    continue
                print(f"  > {cmd}")
                process.stdin.write(cmd + "\n")
                process.stdin.flush()
                time.sleep(1)

            stdout, stderr = process.communicate(timeout=20)
            print("bluetoothctl stdout:")
            print(stdout)
            if stderr:
                print("bluetoothctl stderr:")
                print(stderr)

            if "Connection successful" in stdout or "Connected: yes" in stdout:
                print(
                    "Device successfully paired, trusted, and connected via bluetoothctl."
                )
                return True
            else:
                print(
                    "bluetoothctl commands finished, but device connection not confirmed."
                )
                # Even if "Connection successful" not explicitly found, if bluetoothctl exited cleanly
                # and performed pairing/trusting, it might be enough for Bleak.
                return True

        except subprocess.TimeoutExpired:
            process.kill()
            print("bluetoothctl timed out.")
            return False
        except Exception as e:
            print(f"bluetoothctl pairing failed: {e}")
            return False

    async def _connect_hybrid(self, device_address: str) -> Optional[BleakClient]:
        """Hybrid approach: use bluetoothctl for pairing, Bleak for GATT operations"""
        client = None
        try:
            print("Using hybrid approach: bluetoothctl for pairing, Bleak for GATT...")

            if not self.bluetoothctl_pair_and_trust(device_address):
                raise Exception("bluetoothctl pairing/trusting failed.")

            print("Waiting for device to stabilize after bluetoothctl operations...")
            await asyncio.sleep(5)

            print("Connecting with Bleak for GATT operations...")
            client = BleakClient(
                device_address,
                use_cached=False,
                connection_timeout=45.0,
                disconnected_callback=self._disconnected_callback,
            )

            await client.connect()
            if not client.is_connected:
                raise Exception(
                    "Failed to connect with Bleak after bluetoothctl interactions"
                )

            print("[DEBUG] Accessing services to trigger discovery...")
            await asyncio.sleep(1.5)  # Increased delay after connection

            print("Successfully connected with Bleak after bluetoothctl interaction.")
            return client

        except Exception as e:
            print(f"Hybrid connection failed: {e}")
            if client and client.is_connected:
                await client.disconnect()
            return None

    async def _connect_with_pairing(self, device_id: str) -> Optional[BleakClient]:
        """Connect to device with pairing support"""
        client = None  # Initialize client to None for this scope
        try:
            print(f"[DEBUG] Attempting connection to {device_id}...")
            # Increased timeout for scanning
            device = await BleakScanner.find_device_by_address(device_id, timeout=20.0)
            if not device:
                raise Exception(f"Device {device_id} not found during scan.")

            # Changed security_level to "high" to attempt pairing
            client = BleakClient(
                device,
                security_level="high",
                use_cached=False,
                connection_timeout=30.0,
                disconnected_callback=self._disconnected_callback,
            )

            print(f"[DEBUG] Connecting to {device.address}...")
            await client.connect()

            print(f"[DEBUG] Connected: {client.is_connected}")
            if not client.is_connected:
                raise Exception("Failed to connect to device.")

            print("[DEBUG] Accessing services to trigger discovery...")
            await asyncio.sleep(1.5)  # Increased delay after connection

            # services property will be populated when find_characteristics is called
            print(f"[DEBUG] Services will be discovered implicitly later.")

            return client
        except Exception as e:
            print(f"[DEBUG] Connection failed: {e}")
            if client and client.is_connected:
                await client.disconnect()
            return None  # Return None on failure

    async def find_characteristics(self, client: BleakClient) -> bool:
        """Find and set the required characteristics for provisioning"""
        try:
            print("[DEBUG] Finding provisioning characteristics...")

            # Services should already be discovered by _connect methods implicitly or explicitly
            # Accessing client.services will trigger discovery if not already done.
            services = list(client.services)

            self.control_point_char = None
            self.data_out_char = None
            self.info_char = None

            for service in services:
                if service.uuid.lower().startswith(
                    "14387800"
                ):  # Nordic Provisioning Service UUID prefix
                    for char in service.characteristics:
                        if char.uuid.lower().startswith(
                            "14387802"
                        ):  # Control Point Characteristic UUID prefix
                            self.control_point_char = char
                        elif char.uuid.lower().startswith(
                            "14387803"
                        ):  # Data Out Characteristic UUID prefix
                            self.data_out_char = char
                        elif char.uuid.lower().startswith(
                            "14387801"
                        ):  # Info Characteristic UUID prefix
                            self.info_char = char

            print(
                f"[DEBUG] Control Point Char: {self.control_point_char.uuid if self.control_point_char else 'Not Found'}"
            )
            print(
                f"[DEBUG] Data Out Char: {self.data_out_char.uuid if self.data_out_char else 'Not Found'}"
            )
            print(
                f"[DEBUG] Info Char: {self.info_char.uuid if self.info_char else 'Not Found'}"
            )

            return (
                self.control_point_char is not None and self.data_out_char is not None
            )
        except Exception as e:
            print(f"Error in find_characteristics: {e}")
            return False

    async def _ensure_connected_and_ready(
        self, device_id: str, use_hybrid: bool = False, max_retries: int = 5
    ) -> BleakClient:
        """
        Ensures connection is established and characteristics are found, with retries.
        Raises an exception if connection cannot be established after max_retries.
        """
        for attempt in range(max_retries):
            try:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Connection and setup attempt {attempt + 1}/{max_retries}..."
                )

                # If a client exists and is connected, disconnect it to force a fresh connection
                if self.client and self.client.is_connected:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] Existing client connected. Disconnecting for fresh attempt."
                    )
                    await self.client.disconnect()
                    self.client = None  # Clear existing client
                elif (
                    self.client
                ):  # Client exists but not connected (e.g., previous failure)
                    self.client = None  # Clear it

                if use_hybrid:
                    self.client = await self._connect_hybrid(device_id)
                else:
                    self.client = await self._connect_with_pairing(device_id)

                if not self.client or not self.client.is_connected:
                    raise Exception("Failed to establish Bleak connection.")

                # The crucial part: Calling find_characteristics as an instance method
                if not await self.find_characteristics(self.client):
                    raise Exception("Failed to find required characteristics.")

                print(f"[{time.strftime('%H:%M:%S')}] Device connected and ready.")
                return self.client
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Connection/setup failed: {e}")
                # Ensure client is disconnected and cleared on failure
                if self.client and self.client.is_connected:
                    try:
                        await self.client.disconnect()
                    except Exception as disconnect_e:
                        print(f"Error during explicit disconnect: {disconnect_e}")
                    finally:
                        self.client = None
                elif self.client:  # Client exists but wasn't connected (e.g., BleakClient object but connect failed)
                    self.client = None

                if attempt < max_retries - 1:
                    print(f"[{time.strftime('%H:%M:%S')}] Retrying in 2 seconds...")
                    await asyncio.sleep(2)
                else:
                    raise Exception(
                        f"Failed to connect and setup after {max_retries} attempts."
                    )

    def notification_handler(self, sender_uuid, data):
        """Handle incoming notifications"""
        print(
            f"[{time.strftime('%H:%M:%S')}] Notification from {sender_uuid}: {data.hex()}"
        )
        if len(data) > 0:
            response = self.decode_response(data)
            if response:
                print(f"[{time.strftime('%H:%M:%S')}] Decoded Response: {response}")
                return

            result = self.decode_result(data)
            if result:
                print(f"[{time.strftime('%H:%M:%S')}] Decoded Result: {result}")
                return

            print(
                f"[{time.strftime('%H:%M:%S')}] Could not decode notification as Response or Result."
            )

    def decode_response(self, data):
        """Decode response data"""
        try:
            response = response_pb2.Response()
            response.ParseFromString(data)
            self.responses.append(response)
            return response
        except Exception as e:  # Catch any decoding errors
            # print(f"[{time.strftime('%H:%M:%S')}] Error decoding response: {e}")
            return None

    def decode_result(self, data):
        """Decode result data"""
        try:
            result = result_pb2.Result()
            result.ParseFromString(data)
            self.results.append(result)
            return result
        except Exception as e:  # Catch any decoding errors
            # print(f"[{time.strftime('%H:%M:%S')}] Error decoding result: {e}")
            return None

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover available BLE devices"""
        print("Scanning for BLE devices...")
        devices = await BleakScanner.discover(timeout=10.0)

        all_devices = []
        for device in devices:
            rssi = getattr(device, "rssi", None)
            if rssi is None:
                rssi = getattr(device, "metadata", {}).get("rssi", "Unknown")

            device_info = {
                "address": device.address,
                "name": device.name or "Unknown",
                "rssi": rssi,
            }
            all_devices.append(device_info)

        return all_devices

    async def get_status(
        self, device_id: str, use_hybrid: bool = False
    ) -> DeviceStatus:
        """Get device status via BLE"""
        # Clear previous responses/results
        self.responses = []
        self.results = []

        max_operation_retries = 3  # Retries for the entire get_status operation
        client = None  # Initialize client to None for this function's scope
        for op_attempt in range(max_operation_retries):
            try:
                # Ensure connection and characteristics are ready
                client = await self._ensure_connected_and_ready(device_id, use_hybrid)

                # --- CRITICAL: Subscribe to notifications *before* sending the request ---
                notification_subscribed = await try_subscribe_notify(
                    client, self.data_out_char.uuid, self.notification_handler
                )
                if not notification_subscribed:
                    print(
                        "Warning: Could not subscribe to notifications. Status response may be missed."
                    )
                    # If subscription fails, it's likely a connection issue or device state.
                    # We can't proceed reliably without notifications, so retry the whole operation.
                    raise Exception("Failed to subscribe to notifications.")

                await asyncio.sleep(0.2)

                print("Writing GET_STATUS request...")
                request = request_pb2.Request()
                request.op_code = common_pb2.GET_STATUS
                encoded = request.SerializeToString()

                # Retry the write operation
                max_write_retries = 3
                for write_attempt in range(max_write_retries):
                    try:
                        print(
                            f"[DEBUG] Write attempt {write_attempt + 1}/{max_write_retries} to {self.control_point_char.uuid}"
                        )
                        await client.write_gatt_char(
                            self.control_point_char.uuid, encoded, response=True
                        )
                        print(f"Sent GET_STATUS request: {encoded.hex()}")
                        break
                    except BleakError as e:  # Catch Bleak-specific errors
                        print(f"[DEBUG] Write attempt {write_attempt + 1} failed: {e}")
                        if write_attempt < max_write_retries - 1:
                            print(f"[DEBUG] Retrying write in 0.5 seconds...")
                            await asyncio.sleep(0.5)
                            if (
                                not client.is_connected
                            ):  # Check connection before next retry
                                raise Exception(
                                    "Device disconnected during write retry."
                                )
                        else:
                            raise Exception(
                                f"Failed to write after {max_write_retries} attempts: {e}"
                            )
                    except Exception as e:
                        print(
                            f"[DEBUG] Non-Bleak write attempt {write_attempt + 1} failed: {e}"
                        )
                        raise  # Re-raise other exceptions immediately

                # Wait for response (give enough time for the device to process and notify)
                print("Waiting for response notification...")
                await asyncio.sleep(4)

                # Parse response
                if self.responses:
                    response_pb = self.responses[-1]
                    if response_pb.HasField("status_response"):
                        status_resp = response_pb.status_response
                        state = common_pb2.ConnectionState.Name(status_resp.state)
                        ssid = (
                            status_resp.wifi.ssid.decode("utf-8", errors="ignore")
                            if status_resp.HasField("wifi")
                            and status_resp.wifi.HasField("ssid")
                            else None
                        )
                        ip_address = (
                            status_resp.ipv4_addr
                            if status_resp.HasField("ipv4_addr")
                            else None
                        )
                        bssid = (
                            status_resp.wifi.bssid.hex()
                            if status_resp.HasField("wifi")
                            and status_resp.wifi.HasField("bssid")
                            else None
                        )
                        channel = (
                            status_resp.wifi.channel
                            if status_resp.HasField("wifi")
                            and status_resp.wifi.HasField("channel")
                            else None
                        )

                        return DeviceStatus(
                            state=state,
                            ssid=ssid,
                            ip_address=ip_address,
                            bssid=bssid,
                            channel=channel,
                        )
                    else:
                        print("Received a response, but it's not a status_response.")
                        return DeviceStatus(state="UNKNOWN", ssid="NoStatusResponse")
                else:
                    print("No response notification received from device.")

                # Fallback: try to read info char directly (if it's expected to hold status)
                try:
                    print(
                        f"Attempting direct read from info char ({self.info_char.uuid})..."
                    )
                    value = await client.read_gatt_char(self.info_char.uuid)
                    print(f"Direct read from info char: {value.hex()}")
                    read_result = self.decode_result(value)
                    if read_result:
                        return DeviceStatus(
                            state="READ_INFO", ssid=f"Info: {read_result}"
                        )
                    else:
                        print(
                            "Direct read from info char could not be decoded as Result."
                        )
                except Exception as e:
                    print(f"Direct read from info char failed: {e}")

                return DeviceStatus(state="UNKNOWN_NO_RESPONSE")

            except Exception as e:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Operation attempt {op_attempt + 1} failed: {e}"
                )
                # Ensure client is disconnected and cleared for the next retry
                if client and client.is_connected:
                    try:
                        if self.data_out_char:
                            await client.stop_notify(self.data_out_char.uuid)
                    except Exception as e:
                        print(f"Error stopping notifications: {e}")
                    finally:
                        await client.disconnect()
                        self.client = None
                elif client:  # If client object exists but not connected
                    self.client = None

                if op_attempt < max_operation_retries - 1:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] Retrying entire get_status operation in 3 seconds..."
                    )
                    await asyncio.sleep(3)
                    # Clear responses/results for the next attempt
                    self.responses = []
                    self.results = []
                else:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] Max operation retries reached."
                    )
                    return DeviceStatus(state="ERROR")
            finally:
                # Ensure client is properly disconnected and cleared on final exit from function
                if client and client.is_connected:
                    try:
                        if self.data_out_char:
                            await client.stop_notify(self.data_out_char.uuid)
                    except Exception as e:
                        print(f"Error stopping notifications: {e}")
                    finally:
                        await client.disconnect()
                        self.client = None  # Ensure self.client is also cleared
                elif client:
                    self.client = None

        return DeviceStatus(
            state="ERROR"
        )  # Should only be reached if all retries fail.

    async def scan_networks(
        self, device_id: str, use_hybrid: bool = False
    ) -> List[WiFiNetwork]:
        """Scan for available WiFi networks via BLE"""
        # Clear previous responses/results
        self.responses = []
        self.results = []

        if not hasattr(common_pb2, "START_SCAN"):
            print(
                "Warning: Protobuf files not available or incomplete. Cannot perform WiFi scan."
            )
            return []

        # Similar retry logic as get_status should be applied here for robustness
        client = None
        try:
            client = await self._ensure_connected_and_ready(device_id, use_hybrid)

            notification_subscribed = await try_subscribe_notify(
                client, self.data_out_char.uuid, self.notification_handler
            )
            if not notification_subscribed:
                print(
                    "Warning: Could not subscribe to notifications. Scan results may be missed."
                )
                raise Exception("Failed to subscribe to notifications.")

            await asyncio.sleep(0.2)

            # Send START_SCAN request
            print("Writing START_SCAN request...")
            request = request_pb2.Request()
            request.op_code = common_pb2.START_SCAN

            scan_params = common_pb2.ScanParams()
            scan_params.band = common_pb2.BAND_ANY
            scan_params.passive = False
            scan_params.period_ms = 5000

            request.scan_params.CopyFrom(scan_params)
            encoded = request.SerializeToString()

            await client.write_gatt_char(
                self.control_point_char.uuid, encoded, response=True
            )
            print(f"Sent START_SCAN request: {encoded.hex()}")

            # Wait for scan results (allow more time for multiple notifications)
            print("Waiting for scan result notifications...")
            await asyncio.sleep(8)

            # Parse results
            networks = []
            for result_pb in self.results:
                if result_pb.HasField("scan_record"):
                    scan_record = result_pb.scan_record
                    if scan_record.HasField("wifi"):
                        wifi_info = scan_record.wifi
                        ssid_bytes = wifi_info.ssid
                        ssid_str = ssid_bytes.decode("utf-8", errors="ignore")
                        if not ssid_str and ssid_bytes:
                            ssid_str = ssid_bytes.decode("latin-1", errors="ignore")

                        network = WiFiNetwork(
                            ssid=ssid_str,
                            bssid=wifi_info.bssid.hex(),
                            channel=wifi_info.channel,
                            auth_mode=common_pb2.AuthMode.Name(wifi_info.auth),
                            band=common_pb2.Band.Name(wifi_info.band),
                            rssi=scan_record.rssi
                            if scan_record.HasField("rssi")
                            else None,
                        )
                        networks.append(network)

            return networks
        except Exception as e:
            print(f"Error in scan_networks: {e}")
            return []
        finally:
            if client and client.is_connected:
                try:
                    if self.data_out_char:
                        await client.stop_notify(self.data_out_char.uuid)
                except Exception as e:
                    print(f"Error stopping notifications: {e}")
                finally:
                    await client.disconnect()
                    self.client = None

    async def configure_wifi(
        self,
        device_id: str,
        ssid: str,
        password: str,
        auth_mode: str = "WPA2_PSK",
        volatile: bool = False,
        use_hybrid: bool = False,
    ) -> bool:
        """Configure WiFi settings via BLE"""
        # Clear previous responses/results
        self.responses = []
        self.results = []

        if not hasattr(common_pb2, "SET_CONFIG"):
            print(
                "Warning: Protobuf files not available or incomplete. Cannot configure WiFi."
            )
            return False

        # Similar retry logic as get_status should be applied here for robustness
        client = None
        try:
            client = await self._ensure_connected_and_ready(device_id, use_hybrid)

            notification_subscribed = await try_subscribe_notify(
                client, self.data_out_char.uuid, self.notification_handler
            )
            if not notification_subscribed:
                print(
                    "Warning: Could not subscribe to notifications. Configuration response may be missed."
                )
                raise Exception("Failed to subscribe to notifications.")

            await asyncio.sleep(0.2)

            # Send SET_CONFIG request
            print("Writing SET_CONFIG request...")
            request = request_pb2.Request()
            request.op_code = common_pb2.SET_CONFIG

            wifi_config = request_pb2.WifiConfig()
            wifi_config.passphrase = password.encode("utf-8")
            wifi_config.volatileMemory = volatile

            wifi_info = common_pb2.WifiInfo()
            wifi_info.ssid = ssid.encode("utf-8")

            try:
                wifi_info.auth = getattr(common_pb2.AuthMode, auth_mode)
            except AttributeError:
                print(
                    f"Warning: Unknown authentication mode '{auth_mode}'. Defaulting to WPA2_PSK."
                )
                wifi_info.auth = common_pb2.WPA2_PSK

            wifi_info.channel = 0
            wifi_info.band = common_pb2.BAND_ANY

            wifi_config.wifi.CopyFrom(wifi_info)
            request.config.CopyFrom(wifi_config)

            encoded = request.SerializeToString()
            await client.write_gatt_char(
                self.control_point_char.uuid, encoded, response=True
            )
            print(f"Sent SET_CONFIG request: {encoded.hex()}")

            print("Waiting for configuration response notification...")
            await asyncio.sleep(5)

            if self.responses:
                response_pb = self.responses[-1]
                if response_pb.op_code == common_pb2.SET_CONFIG:
                    return response_pb.status == common_pb2.SUCCESS
                else:
                    print(
                        f"Received response with unexpected op_code: {common_pb2.OpCode.Name(response_pb.op_code)}"
                    )
                    return False
            else:
                print("No response notification received for configuration.")

            return False
        except Exception as e:
            print(f"Error in configure_wifi: {e}")
            return False
        finally:
            if client and client.is_connected:
                try:
                    if self.data_out_char:
                        await client.stop_notify(self.data_out_char.uuid)
                except Exception as e:
                    print(f"Error stopping notifications: {e}")
                finally:
                    await client.disconnect()
                    self.client = None

    async def forget_config(self, device_id: str, use_hybrid: bool = False) -> bool:
        """Forget WiFi configuration via BLE"""
        # Clear previous responses/results
        self.responses = []
        self.results = []

        if not hasattr(common_pb2, "FORGET_CONFIG"):
            print(
                "Warning: Protobuf files not available or incomplete. Cannot forget WiFi configuration."
            )
            return False

        # Similar retry logic as get_status should be applied here for robustness
        client = None
        try:
            client = await self._ensure_connected_and_ready(device_id, use_hybrid)

            notification_subscribed = await try_subscribe_notify(
                client, self.data_out_char.uuid, self.notification_handler
            )
            if not notification_subscribed:
                print(
                    "Warning: Could not subscribe to notifications. Forget response may be missed."
                )
                raise Exception("Failed to subscribe to notifications.")

            await asyncio.sleep(0.2)

            # Send FORGET_CONFIG request
            print("Writing FORGET_CONFIG request...")
            request = request_pb2.Request()
            request.op_code = common_pb2.FORGET_CONFIG
            encoded = request.SerializeToString()
            await client.write_gatt_char(
                self.control_point_char.uuid, encoded, response=True
            )
            print(f"Sent FORGET_CONFIG request: {encoded.hex()}")

            print("Waiting for forget configuration response notification...")
            await asyncio.sleep(3)

            if self.responses:
                response_pb = self.responses[-1]
                if response_pb.op_code == common_pb2.FORGET_CONFIG:
                    return response_pb.status == common_pb2.SUCCESS
                else:
                    print(
                        f"Received response with unexpected op_code: {common_pb2.OpCode.Name(response_pb.op_code)}"
                    )
                    return False
            else:
                print("No response notification received for forget configuration.")

            return False
        except Exception as e:
            print(f"Error in forget_config: {e}")
            return False
        finally:
            if client and client.is_connected:
                try:
                    if self.data_out_char:
                        await client.stop_notify(self.data_out_char.uuid)
                except Exception as e:
                    print(f"Error stopping notifications: {e}")
                finally:
                    await client.disconnect()
                    self.client = None


async def try_subscribe_notify(client, char_uuid, handler, retries=3, delay=0.5):
    """
    Attempts to subscribe to a characteristic's notifications with retries.
    This is made more robust by checking if client is connected before each attempt.
    """
    for attempt in range(retries):
        if not client.is_connected:
            print(
                f"[{time.strftime('%H:%M:%S')}] Client disconnected. Cannot subscribe."
            )
            return False
        try:
            print(
                f"[{time.strftime('%H:%M:%S')}] Attempt {attempt + 1}/{retries} to subscribe to notifications on {char_uuid}..."
            )
            await asyncio.sleep(0.1)  # Added small delay before subscribing
            await client.start_notify(char_uuid, handler)
            print(
                f"[{time.strftime('%H:%M:%S')}] Subscribed to notifications on {char_uuid}"
            )
            return True
        except Exception as e:
            print(
                f"[{time.strftime('%H:%M:%S')}] Attempt {attempt + 1} to subscribe failed: {type(e).__name__}: {e}"
            )
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    print(
        f"[{time.strftime('%H:%M:%S')}] Failed to subscribe to notifications after {retries} attempts on {char_uuid}"
    )
    return False


class SoftAPProvisioningClient(ProvisioningClient):
    """SoftAP (Wi-Fi) provisioning client"""

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover devices via SoftAP"""
        print("SoftAP provisioning not yet implemented")
        return []

    async def get_status(
        self, device_id: str, use_hybrid: bool = False
    ) -> DeviceStatus:
        """Get device status via SoftAP"""
        raise NotImplementedError("SoftAP provisioning not yet implemented")

    async def scan_networks(
        self, device_id: str, use_hybrid: bool = False
    ) -> List[WiFiNetwork]:
        """Scan for available WiFi networks via SoftAP"""
        raise NotImplementedError("SoftAP provisioning not yet implemented")

    async def configure_wifi(
        self,
        device_id: str,
        ssid: str,
        password: str,
        auth_mode: str = "WPA2_PSK",
        volatile: bool = False,
        use_hybrid: bool = False,
    ) -> bool:
        """Configure WiFi settings via SoftAP"""
        raise NotImplementedError("SoftAP provisioning not yet implemented")

    async def forget_config(self, device_id: str, use_hybrid: bool = False) -> bool:
        """Forget WiFi configuration via SoftAP"""
        raise NotImplementedError("SoftAP provisioning not yet implemented")


class NFCProvisioningClient(ProvisioningClient):
    """NFC provisioning client"""

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover devices via NFC"""
        print("NFC provisioning not yet implemented")
        return []

    async def get_status(
        self, device_id: str, use_hybrid: bool = False
    ) -> DeviceStatus:
        """Get device status via NFC"""
        raise NotImplementedError("NFC provisioning not yet implemented")

    async def scan_networks(
        self, device_id: str, use_hybrid: bool = False
    ) -> List[WiFiNetwork]:
        """Scan for available WiFi networks via NFC"""
        raise NotImplementedError("NFC provisioning not yet implemented")

    async def configure_wifi(
        self,
        device_id: str,
        ssid: str,
        password: str,
        auth_mode: str = "WPA2_PSK",
        volatile: bool = False,
        use_hybrid: bool = False,
    ) -> bool:
        """Configure WiFi settings via NFC"""
        raise NotImplementedError("NFC provisioning not yet implemented")

    async def forget_config(self, device_id: str, use_hybrid: bool = False) -> bool:
        """Forget WiFi configuration via NFC"""
        raise NotImplementedError("NFC provisioning not yet implemented")


def get_provisioning_client(mode: str) -> ProvisioningClient:
    """Get the appropriate provisioning client based on mode"""
    if mode == "ble":
        return BLEProvisioningClient()
    elif mode == "softap":
        return SoftAPProvisioningClient()
    elif mode == "nfc":
        return NFCProvisioningClient()
    else:
        raise ValueError(f"Unknown provisioning mode: {mode}")


async def cmd_discover(args):
    """Discover available devices"""
    client = get_provisioning_client(args.mode)
    devices = await client.discover_devices()

    if not devices:
        print("No devices found")
        return

    print(f"Found {len(devices)} device(s):")
    for i, device in enumerate(devices, 1):
        print(
            f"{i}. {device['name']} ({device['address']}) - RSSI: {device['rssi']} dBm"
        )


async def cmd_status(args):
    """Get device status"""
    client = get_provisioning_client(args.mode)
    status = await client.get_status(
        args.device, use_hybrid=getattr(args, "hybrid", False)
    )

    print(f"Device Status:")
    print(f"  State: {status.state}")
    if status.ssid:
        print(f"  SSID: {status.ssid}")
    if status.ip_address:
        print(f"  IP Address: {status.ip_address}")
    if status.bssid:
        print(f"  BSSID: {status.bssid}")
    if status.channel:
        print(f"  Channel: {status.channel}")


async def cmd_scan(args):
    """Scan for WiFi networks"""
    client = get_provisioning_client(args.mode)
    networks = await client.scan_networks(
        args.device, use_hybrid=getattr(args, "hybrid", False)
    )

    if not networks:
        print("No networks found")
        return

    print(f"Found {len(networks)} network(s):")
    for i, network in enumerate(networks, 1):
        rssi_str = f" ({network.rssi} dBm)" if network.rssi else ""
        print(
            f"{i}. {network.ssid} - {network.auth_mode} - Channel {network.channel}{rssi_str}"
        )


async def cmd_configure(args):
    """Configure WiFi settings"""
    client = get_provisioning_client(args.mode)
    success = await client.configure_wifi(
        args.device,
        args.ssid,
        args.password,
        args.auth_mode,
        args.volatile,
        use_hybrid=getattr(args, "hybrid", False),
    )

    if success:
        print(f"Successfully configured WiFi for SSID: {args.ssid}")
    else:
        print("Failed to configure WiFi")
        sys.exit(1)


async def cmd_forget(args):
    """Forget WiFi configuration"""
    client = get_provisioning_client(args.mode)
    success = await client.forget_config(
        args.device, use_hybrid=getattr(args, "hybrid", False)
    )

    if success:
        print("Successfully forgot WiFi configuration")
    else:
        print("Failed to forget WiFi configuration")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="nRF Wi-Fi Provisioner CLI - Provision nRF 7002 devices to WiFi networks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ble discover
  %(prog)s ble status --device AA:BB:CC:DD:EE:FF
  %(prog)s ble scan --device AA:BB:CC:DD:EE:FF
  %(prog)s ble configure --device AA:BB:CC:DD:EE:FF --ssid "MyWiFi" --password "mypassword"
  %(prog)s ble forget --device AA:BB:CC:DD:EE:FF
  %(prog)s ble status --device AA:BB:CC:DD:EE:FF --hybrid
		""",
    )

    subparsers = parser.add_subparsers(dest="mode", help="Provisioning mode")

    ble_parser = subparsers.add_parser("ble", help="Bluetooth LE provisioning")
    ble_subparsers = ble_parser.add_subparsers(
        dest="command", help="Available commands"
    )

    discover_parser = ble_subparsers.add_parser(
        "discover", help="Discover available devices"
    )

    status_parser = ble_subparsers.add_parser("status", help="Get device status")
    status_parser.add_argument("--device", required=True, help="Device address/ID")
    status_parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid approach (bluetoothctl for pairing, Bleak for notifications)",
    )

    scan_parser = ble_subparsers.add_parser("scan", help="Scan for WiFi networks")
    scan_parser.add_argument("--device", required=True, help="Device address/ID")
    scan_parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid approach (bluetoothctl for pairing, Bleak for notifications)",
    )

    configure_parser = ble_subparsers.add_parser(
        "configure", help="Configure WiFi settings"
    )
    configure_parser.add_argument("--device", required=True, help="Device address/ID")
    configure_parser.add_argument("--ssid", required=True, help="WiFi SSID")
    configure_parser.add_argument("--password", required=True, help="WiFi password")
    configure_parser.add_argument(
        "--auth-mode",
        default="WPA2_PSK",
        choices=[
            "OPEN",
            "WEP",
            "WPA_PSK",
            "WPA2_PSK",
            "WPA_WPA2_PSK",
            "WPA2_ENTERPRISE",
        ],
        help="Authentication mode",
    )
    configure_parser.add_argument(
        "--volatile", action="store_true", help="Store configuration in volatile memory"
    )
    configure_parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid approach (bluetoothctl for pairing, Bleak for notifications)",
    )

    forget_parser = ble_subparsers.add_parser(
        "forget", help="Forget WiFi configuration"
    )
    forget_parser.add_argument("--device", required=True, help="Device address/ID")
    forget_parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid approach (bluetoothctl for pairing, Bleak for notifications)",
    )

    softap_parser = subparsers.add_parser("softap", help="SoftAP (Wi-Fi) provisioning")
    softap_parser.add_argument(
        "command", choices=["discover"], help="Available commands"
    )

    nfc_parser = subparsers.add_parser("nfc", help="NFC provisioning")
    nfc_parser.add_argument("command", choices=["discover"], help="Available commands")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        return

    if args.mode == "ble" and not args.command:
        ble_parser.print_help()
        return

    try:
        if args.mode == "ble":
            if args.command == "discover":
                asyncio.run(cmd_discover(args))
            elif args.command == "status":
                asyncio.run(cmd_status(args))
            elif args.command == "scan":
                asyncio.run(cmd_scan(args))
            elif args.command == "configure":
                asyncio.run(cmd_configure(args))
            elif args.command == "forget":
                asyncio.run(cmd_forget(args))
        elif args.mode == "softap":
            print("SoftAP provisioning not yet implemented")
        elif args.mode == "nfc":
            print("NFC provisioning not yet implemented")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
