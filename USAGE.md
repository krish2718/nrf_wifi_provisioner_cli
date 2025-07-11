# nRF Wi-Fi Provisioner CLI Usage Guide

This CLI tool mirrors the functionality of the Nordic Android nRF Wi-Fi Provisioner app, providing command-line access to provision nRF 7002 devices to WiFi networks. It supports Bluetooth LE provisioning with automatic characteristic discovery and hybrid pairing modes.

## Installation

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y protobuf-compiler bluetooth bluez
```

**macOS:**
```bash
brew install protobuf
```

### Python Dependencies

```bash
pip install bleak protobuf
```

### Quick Setup

```bash
# Install all dependencies and setup
make install-python-deps
make proto-check
```

## Basic Usage

### 1. Discover Available Devices

```bash
# Discover BLE devices
python3 nrf_wifi_provisioner_cli.py ble discover

# Example output:
# Scanning for BLE devices...
# Found 1 device(s):
# 1. nRF7002-DK (AA:BB:CC:DD:EE:FF) - RSSI: -45 dBm
```

### 2. Get Device Status

```bash
# Get device status via BLE
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF

# Example output:
# Device Status:
#   State: DISCONNECTED
#   SSID: MyWiFi
#   IP Address: 192.168.1.100
```

### 3. Scan for WiFi Networks

```bash
# Scan for available WiFi networks
python3 nrf_wifi_provisioner_cli.py ble scan --device AA:BB:CC:DD:EE:FF

# Example output:
# Found 3 network(s):
# 1. MyWiFi - WPA2_PSK - Channel 6 (-45 dBm)
# 2. GuestWiFi - WPA2_PSK - Channel 11 (-52 dBm)
# 3. OfficeWiFi - WPA2_PSK - Channel 1 (-60 dBm)
```

### 4. Configure WiFi Settings

```bash
# Configure WiFi with basic settings
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword"

# Configure with specific auth mode
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --auth-mode WPA2_PSK

# Configure with volatile memory (temporary)
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --volatile
```

### 5. Forget WiFi Configuration

```bash
# Remove stored WiFi configuration
python3 nrf_wifi_provisioner_cli.py ble forget --device AA:BB:CC:DD:EE:FF

# Example output:
# Successfully forgot WiFi configuration
```

## Advanced Features

### Hybrid Mode

Use bluetoothctl for pairing and Bleak for notifications when standard BLE connection fails:

```bash
# Use hybrid mode for better compatibility
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF --hybrid

# Configure WiFi with hybrid mode
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --hybrid
```

### Volatile Configuration

Configure WiFi temporarily without saving to device memory:

```bash
# Temporary configuration (not saved)
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --volatile
```

### Verbose Logging

Enable detailed logging for debugging:

```bash
# Enable verbose output
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF --verbose

# Verbose with hybrid mode
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --hybrid \
  --verbose
```

## Available Authentication Modes

- `OPEN` - Open network (no password)
- `WEP` - WEP encryption
- `WPA_PSK` - WPA Personal
- `WPA2_PSK` - WPA2 Personal (default)
- `WPA_WPA2_PSK` - WPA/WPA2 Personal
- `WPA2_ENTERPRISE` - WPA2 Enterprise

## Command Structure

```
python3 nrf_wifi_provisioner_cli.py <mode> <command> [options]
```

### Modes
- `ble` - Bluetooth LE provisioning (fully implemented)
- `softap` - SoftAP (Wi-Fi) provisioning (planned)
- `nfc` - NFC provisioning (planned)

### Commands
- `discover` - Find available devices
- `status` - Get device connection status
- `scan` - Scan for WiFi networks
- `configure` - Configure WiFi settings
- `forget` - Remove WiFi configuration

### Global Options
- `--verbose` - Enable verbose logging
- `--hybrid` - Use hybrid mode (bluetoothctl + Bleak)

### BLE Command Options
- `--device <address>` - Device BLE address (required)
- `--ssid <ssid>` - WiFi network name
- `--password <password>` - WiFi password
- `--auth-mode <mode>` - Authentication mode
- `--volatile` - Use volatile memory (temporary)

## Examples

### Complete Workflow

```bash
# 1. Discover devices
python3 nrf_wifi_provisioner_cli.py ble discover

# 2. Check device status
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF

# 3. Scan for networks
python3 nrf_wifi_provisioner_cli.py ble scan --device AA:BB:CC:DD:EE:FF

# 4. Configure WiFi
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword"

# 5. Verify configuration
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF
```

### Troubleshooting Commands

```bash
# Get help for main command
python3 nrf_wifi_provisioner_cli.py --help

# Get help for BLE commands
python3 nrf_wifi_provisioner_cli.py ble --help

# Get help for specific command
python3 nrf_wifi_provisioner_cli.py ble configure --help

# Verbose discovery for debugging
python3 nrf_wifi_provisioner_cli.py ble discover --verbose
```

## Makefile Integration

The project includes a comprehensive Makefile for easy usage:

```bash
# Quick setup
make install-python-deps
make proto-check

# Common operations
make ble-discover
make ble-status DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF
make ble-scan DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF
make ble-configure DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF SSID=MyWiFi PASSWORD=mypassword
make ble-forget DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF

# Development
make test
make dev-setup
```

## Protocol Buffer Support

The CLI uses generated protobuf files for message serialization. The generated files are located in the `generated/` folder:

- `common_pb2.py` - Shared message structures
- `request_pb2.py` - Commands sent to devices
- `response_pb2.py` - Status responses from devices
- `result_pb2.py` - Scan results and connection updates
- `version_pb2.py` - Version information

### Regenerating Protobuf Files

If you have updated .proto files:

```bash
# Generate protobuf files
make proto

# Or manually
python3 generate_proto.py ./protos ./generated
```

## Error Handling

The CLI provides clear error messages for common issues:

### Common Errors and Solutions

**Device not found:**
```
Error: Device AA:BB:CC:DD:EE:FF not found
```
- Check device address and ensure device is powered on
- Verify Bluetooth is enabled on your system

**Connection failed:**
```
Error: Failed to connect to device AA:BB:CC:DD:EE:FF
```
- Ensure device supports the Provision Service
- Try using hybrid mode: `--hybrid`
- Check if device is already connected to another client

**Characteristics not found:**
```
Error: Required characteristics not found
```
- Device may use different UUIDs
- Verify device implements Nordic WiFi Provisioning Protocol
- Check device documentation for correct service UUIDs

**Authentication failed:**
```
Error: WiFi authentication failed
```
- Check WiFi credentials and network availability
- Verify authentication mode matches network requirements
- Ensure device is within range of the WiFi network

**Protobuf import errors:**
```
Warning: Protobuf files not found
```
- Run `make proto` to generate protobuf files
- Ensure protoc is installed: `make proto-check`
- Check that .proto files are in the correct location

## Integration

This CLI tool can be easily integrated into:

- **Automation scripts**: Use in CI/CD pipelines
- **Development workflows**: Quick device testing
- **Headless systems**: Server environments without GUI
- **Testing frameworks**: Automated device provisioning tests

## Comparison with Android App

| Feature | Android App | CLI Tool |
|---------|-------------|----------|
| BLE Provisioning | ✅ | ✅ |
| SoftAP Provisioning | ✅ | 🔄 (planned) |
| NFC Provisioning | ✅ | 🔄 (planned) |
| Device Discovery | ✅ | ✅ |
| Network Scanning | ✅ | ✅ |
| WiFi Configuration | ✅ | ✅ |
| Status Monitoring | ✅ | ✅ |
| Hybrid Mode | ❌ | ✅ |
| Volatile Configuration | ❌ | ✅ |
| Automation | ❌ | ✅ |
| Headless Operation | ❌ | ✅ |
| Script Integration | ❌ | ✅ |
| Verbose Logging | ❌ | ✅ |

✅ = Implemented  
🔄 = Planned  
❌ = Not available

## Advanced Usage

### Custom Protobuf Messages

The CLI supports custom protobuf message formats. If your device uses different message structures:

1. Update the .proto files in the `protos/` folder
2. Regenerate protobuf files: `make proto`
3. Update the message handling in the CLI code

### Extending the CLI

To add new commands or provisioning modes:

1. Implement new client classes in `nrf_wifi_provisioner_cli.py`
2. Add command handlers in the main function
3. Update the argument parser for new options
4. Add corresponding Makefile targets

### Debugging

For advanced debugging:

```bash
# Enable Python debugger
python3 -m pdb nrf_wifi_provisioner_cli.py ble discover

# Enable Bleak debug logging
BLEAK_LOGGING=1 python3 nrf_wifi_provisioner_cli.py ble discover

# Verbose with all debug info
python3 nrf_wifi_provisioner_cli.py ble discover --verbose
```
