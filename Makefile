# Makefile for Proto Generation and BLE Provisioning
# Usage: make <target>

# Configuration
PROTO_FOLDER ?= ./protos
OUTPUT_FOLDER ?= ./generated
PYTHON = python3
PIP = pip3

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  proto          - Generate Python files from .proto files"
	@echo "  proto-clean    - Clean generated proto files"
	@echo "  proto-check    - Check if protoc is installed"
	@echo "  install-deps   - Install system dependencies (Ubuntu/Debian)"
	@echo "  install-deps-mac - Install system dependencies (macOS)"
	@echo "  install-python-deps - Install Python dependencies"
	@echo "  ble-discover   - Discover BLE devices"
	@echo "  ble-status     - Get device status (requires DEVICE_ADDRESS)"
	@echo "  ble-scan       - Scan for WiFi networks (requires DEVICE_ADDRESS)"
	@echo "  ble-configure  - Configure WiFi (requires DEVICE_ADDRESS, SSID, PASSWORD)"
	@echo "  ble-forget     - Forget WiFi configuration (requires DEVICE_ADDRESS)"
	@echo "  clean          - Clean all generated files"
	@echo "  test           - Run basic tests"
	@echo ""
	@echo "Examples:"
	@echo "  make proto"
	@echo "  make ble-discover"
	@echo "  make ble-status DEVICE_ADDRESS=EE:F9:74:E2:21:B4"
	@echo "  make ble-configure DEVICE_ADDRESS=EE:F9:74:E2:21:B4 SSID=MyWiFi PASSWORD=mypassword"

# Proto generation targets
.PHONY: proto proto-clean proto-check
proto: generate_proto.py
	@echo "Generating Python files from .proto files..."
	$(PYTHON) generate_proto.py $(PROTO_FOLDER) $(OUTPUT_FOLDER) --verbose

proto-clean:
	@echo "Cleaning generated proto files..."
	$(PYTHON) generate_proto.py $(PROTO_FOLDER) $(OUTPUT_FOLDER) --clean --verbose

proto-check:
	@echo "Checking protoc installation..."
	@if command -v protoc >/dev/null 2>&1; then \
		echo "✓ protoc is installed: $$(protoc --version)"; \
	else \
		echo "✗ protoc is not installed. Run 'make install-deps' or 'make install-deps-mac'"; \
	fi

# Dependency installation
.PHONY: install-deps install-deps-mac install-python-deps
install-deps:
	@echo "Installing system dependencies (Ubuntu/Debian)..."
	sudo apt-get update
	sudo apt-get install -y protobuf-compiler bluetooth bluez

install-deps-mac:
	@echo "Installing system dependencies (macOS)..."
	brew install protobuf

install-python-deps:
	@echo "Installing Python dependencies..."
	$(PIP) install bleak protobuf

# BLE provisioning targets
.PHONY: ble-discover ble-status ble-scan ble-configure ble-forget
ble-discover:
	@echo "Discovering BLE devices..."
	$(PYTHON) nrf_wifi_provisioner_cli.py ble discover

ble-status:
	@if [ -z "$(DEVICE_ADDRESS)" ]; then \
		echo "Error: DEVICE_ADDRESS is required. Example: make ble-status DEVICE_ADDRESS=EE:F9:74:E2:21:B4"; \
		exit 1; \
	fi
	@echo "Getting device status for $(DEVICE_ADDRESS)..."
	$(PYTHON) nrf_wifi_provisioner_cli.py ble status --device $(DEVICE_ADDRESS)

ble-scan:
	@if [ -z "$(DEVICE_ADDRESS)" ]; then \
		echo "Error: DEVICE_ADDRESS is required. Example: make ble-scan DEVICE_ADDRESS=EE:F9:74:E2:21:B4"; \
		exit 1; \
	fi
	@echo "Scanning for WiFi networks on $(DEVICE_ADDRESS)..."
	$(PYTHON) nrf_wifi_provisioner_cli.py ble scan --device $(DEVICE_ADDRESS)

ble-configure:
	@if [ -z "$(DEVICE_ADDRESS)" ] || [ -z "$(SSID)" ] || [ -z "$(PASSWORD)" ]; then \
		echo "Error: DEVICE_ADDRESS, SSID, and PASSWORD are required."; \
		echo "Example: make ble-configure DEVICE_ADDRESS=EE:F9:74:E2:21:B4 SSID=MyWiFi PASSWORD=mypassword"; \
		exit 1; \
	fi
	@echo "Configuring WiFi for $(SSID) on $(DEVICE_ADDRESS)..."
	$(PYTHON) nrf_wifi_provisioner_cli.py ble configure --device $(DEVICE_ADDRESS) --ssid "$(SSID)" --password "$(PASSWORD)"

ble-forget:
	@if [ -z "$(DEVICE_ADDRESS)" ]; then \
		echo "Error: DEVICE_ADDRESS is required. Example: make ble-forget DEVICE_ADDRESS=EE:F9:74:E2:21:B4"; \
		exit 1; \
	fi
	@echo "Forgetting WiFi configuration on $(DEVICE_ADDRESS)..."
	$(PYTHON) nrf_wifi_provisioner_cli.py ble forget --device $(DEVICE_ADDRESS)

# Utility targets
.PHONY: clean test
clean:
	@echo "Cleaning all generated files..."
	rm -rf $(OUTPUT_FOLDER)
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

test:
	@echo "Running basic tests..."
	@echo "1. Checking protoc installation..."
	@make proto-check
	@echo "2. Checking Python dependencies..."
	@$(PYTHON) -c "import bleak, google.protobuf; print('✓ Dependencies OK')" || echo "✗ Missing dependencies"
	@echo "3. Testing proto generation (if protos exist)..."
	@if [ -d "$(PROTO_FOLDER)" ] && [ -n "$$(ls $(PROTO_FOLDER)/*.proto 2>/dev/null)" ]; then \
		make proto; \
	else \
		echo "No proto files found in $(PROTO_FOLDER)"; \
	fi

# Development targets
.PHONY: dev-setup dev-test
dev-setup: install-python-deps proto-check
	@echo "Development environment setup complete"

dev-test: test ble-discover
	@echo "Development tests complete"

# Documentation
.PHONY: docs
docs:
	@echo "Generating documentation..."
	@if [ -f "README.md" ]; then \
		echo "✓ README.md exists"; \
	else \
		echo "✗ README.md not found"; \
	fi
	@if [ -f "USAGE.md" ]; then \
		echo "✓ USAGE.md exists"; \
	else \
		echo "✗ USAGE.md not found"; \
	fi

# Quick start workflow
.PHONY: quick-start
quick-start: install-python-deps proto-check
	@echo "Quick start setup complete!"
	@echo "Next steps:"
	@echo "1. Run 'make ble-discover' to find your device"
	@echo "2. Run 'make ble-status DEVICE_ADDRESS=<your-device-address>' to check status"
	@echo "3. Run 'make ble-configure DEVICE_ADDRESS=<your-device-address> SSID=<your-wifi> PASSWORD=<your-password>' to configure WiFi"
