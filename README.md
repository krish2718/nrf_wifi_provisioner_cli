# nRF Wi-Fi Provisioner CLI

A command-line tool for provisioning nRF 7002 devices to a Wi-Fi network, mirroring the functionality of the Nordic Android nRF Wi-Fi Provisioner app. This tool supports Bluetooth LE provisioning and provides a comprehensive CLI interface for device management.

## Project Structure

```
nrf_wifi_provisioner_cli/
├── nrf_wifi_provisioner_cli.py    # Main CLI application
├── generate_proto.py              # Protobuf generation script
├── Makefile                       # Build and utility targets
├── generated/                     # Generated protobuf files
│   ├── __init__.py
│   ├── common_pb2.py
│   ├── request_pb2.py
│   ├── response_pb2.py
│   ├── result_pb2.py
│   └── version_pb2.py
├── README.md                      # This file
├── USAGE.md                       # Detailed usage guide
└── .gitignore                     # Git ignore rules
```

## Features

- **Bluetooth LE Provisioning**: Full BLE support for device discovery and WiFi configuration
- **Hybrid Mode**: Combines bluetoothctl for pairing with Bleak for notifications
- **Automatic Characteristic Discovery**: Finds correct BLE characteristics automatically
- **Protocol Buffer Support**: Uses generated protobuf classes for message serialization
- **Comprehensive CLI**: Complete command-line interface with subcommands
- **Error Handling**: Robust error handling and retry mechanisms
- **Cross-platform**: Works on Linux, macOS, and Windows

## Prerequisites

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

## Quick Start

### 1. Setup

```bash
# Install dependencies
make install-python-deps

# Check protoc installation
make proto-check

# Generate protobuf files (if you have .proto files)
make proto
```

### 2. Discover Devices

```bash
# Discover available BLE devices
python3 nrf_wifi_provisioner_cli.py ble discover

# Or use make
make ble-discover
```

### 3. Configure WiFi

```bash
# Configure WiFi on a device
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword"

# Or use make
make ble-configure DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF SSID=MyWiFi PASSWORD=mypassword
```

## Available Commands

### Device Discovery
```bash
python3 nrf_wifi_provisioner_cli.py ble discover
```

### Device Status
```bash
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF
```

### WiFi Network Scanning
```bash
python3 nrf_wifi_provisioner_cli.py ble scan --device AA:BB:CC:DD:EE:FF
```

### WiFi Configuration
```bash
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --auth-mode WPA2_PSK \
  --volatile
```

### Forget WiFi Configuration
```bash
python3 nrf_wifi_provisioner_cli.py ble forget --device AA:BB:CC:DD:EE:FF
```

## Authentication Modes

- `OPEN` - Open network (no password)
- `WEP` - WEP encryption
- `WPA_PSK` - WPA Personal
- `WPA2_PSK` - WPA2 Personal (default)
- `WPA_WPA2_PSK` - WPA/WPA2 Personal
- `WPA2_ENTERPRISE` - WPA2 Enterprise

## Advanced Features

### Hybrid Mode
Use bluetoothctl for pairing and Bleak for notifications:
```bash
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF --hybrid
```

### Volatile Configuration
Configure WiFi temporarily (not saved to device memory):
```bash
python3 nrf_wifi_provisioner_cli.py ble configure \
  --device AA:BB:CC:DD:EE:FF \
  --ssid "MyWiFi" \
  --password "mypassword" \
  --volatile
```

## Makefile Targets

The project includes a comprehensive Makefile for common operations:

```bash
# Generate protobuf files
make proto

# Discover devices
make ble-discover

# Get device status
make ble-status DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF

# Scan for networks
make ble-scan DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF

# Configure WiFi
make ble-configure DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF SSID=MyWiFi PASSWORD=mypassword

# Forget configuration
make ble-forget DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF

# Install dependencies
make install-deps

# Run tests
make test
```

## Protocol Details

The CLI uses Protocol Buffers for message serialization, following the Nordic WiFi Provisioning Protocol. The message types include:

- **Request** - Commands sent to the device
- **Response** - Status responses from the device
- **Result** - Scan results and connection status updates
- **Common** - Shared message structures
- **Version** - Version information

## Device Compatibility

The tool is designed to work with devices that implement the Nordic WiFi Provisioning Protocol using a custom Provision Service. The expected BLE service structure:

```
Service: 1827 (BT_UUID_PROV)
├── Characteristic: 2A6E (BT_UUID_PROV_CONTROL_POINT) - Write/Indicate
├── Characteristic: 2A6F (BT_UUID_PROV_DATA_OUT) - Notify
└── Characteristic: 2A6D (BT_UUID_PROV_INFO) - Read
```

## Troubleshooting

### Common Issues

**Device Not Found:**
- Ensure the device is powered on and advertising
- Check that the device address is correct
- Verify Bluetooth is enabled on your system

**Connection Failed:**
- Ensure the device supports the Provision Service
- Check that the device is not already connected to another client
- Try using hybrid mode: `--hybrid`

**Characteristics Not Found:**
- The tool automatically discovers characteristics
- Check if your device uses different UUIDs
- Verify the device implements the Nordic WiFi Provisioning Protocol

**Protobuf Errors:**
- Run `make proto` to generate protobuf files
- Ensure protoc is installed: `make proto-check`
- Check that .proto files are in the correct location

### Debug Mode

Enable verbose logging:
```bash
python3 nrf_wifi_provisioner_cli.py ble status --device AA:BB:CC:DD:EE:FF --verbose
```

## Development

### Project Setup

```bash
# Clone the repository
git clone <repository-url>
cd nrf_wifi_provisioner_cli

# Setup development environment
make dev-setup

# Run tests
make dev-test
```

### Adding New Features

1. **New Provisioning Modes**: Implement new client classes in `nrf_wifi_provisioner_cli.py`
2. **Protocol Updates**: Update protobuf definitions and regenerate files
3. **CLI Commands**: Add new command handlers in the main function

### Code Style

The project follows typical OSS styles like Linux kernel and Zephyr RTOS:
- Clear function and variable naming
- Comprehensive error handling
- Detailed logging and debugging support
- Modular design with separation of concerns

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the code style guidelines
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Check the troubleshooting section
- Review the USAGE.md file for detailed examples
- Open an issue on the project repository
