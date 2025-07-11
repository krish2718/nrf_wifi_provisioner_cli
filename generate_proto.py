#!/usr/bin/env python3
"""
Proto to Python Generator Script

This script generates Python protobuf files from .proto files in a given folder.
It handles multiple proto files, dependencies, and provides a clean interface.

Usage:
    python3 generate_proto.py <proto_folder> [output_folder]

Examples:
    python3 generate_proto.py ./protos
    python3 generate_proto.py ./protos ./generated
    python3 generate_proto.py ./protos --clean
"""

import os
import sys
import subprocess
import argparse
import glob
from pathlib import Path
from typing import List, Optional


def check_protoc_installed() -> bool:
    """Check if protoc compiler is installed and available"""
    try:
        result = subprocess.run(
            ["protoc", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def find_proto_files(proto_folder: str) -> List[str]:
    """Find all .proto files in the given folder"""
    proto_path = Path(proto_folder)
    if not proto_path.exists():
        raise FileNotFoundError(f"Proto folder not found: {proto_folder}")

    proto_files = list(proto_path.glob("*.proto"))
    if not proto_files:
        raise FileNotFoundError(f"No .proto files found in: {proto_folder}")

    return [str(f) for f in proto_files]


def generate_python_files(
    proto_files: List[str], output_folder: str, proto_folder: str, verbose: bool = False
) -> bool:
    """Generate Python files from proto files"""

    # Create output directory if it doesn't exist
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    success_count = 0
    total_count = len(proto_files)

    for proto_file in proto_files:
        try:
            if verbose:
                print(f"Generating Python file for: {proto_file}")

            # Run protoc command
            cmd = [
                "protoc",
                f"--python_out={output_folder}",
                f"--proto_path={proto_folder}",
                proto_file,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                success_count += 1
                proto_name = Path(proto_file).stem
                py_file = output_path / f"{proto_name}_pb2.py"
                if verbose:
                    print(f"  ✓ Generated: {py_file}")
            else:
                print(f"  ✗ Failed to generate {proto_file}:")
                print(f"    Error: {result.stderr}")

        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout generating {proto_file}")
        except Exception as e:
            print(f"  ✗ Error generating {proto_file}: {e}")

    return success_count == total_count


def clean_generated_files(output_folder: str, verbose: bool = False) -> None:
    """Remove all generated Python files"""
    output_path = Path(output_folder)
    if not output_path.exists():
        return

    # Remove all *_pb2.py files
    for py_file in output_path.glob("*_pb2.py"):
        try:
            py_file.unlink()
            if verbose:
                print(f"Removed: {py_file}")
        except Exception as e:
            print(f"Failed to remove {py_file}: {e}")


def create_makefile(output_folder: str, proto_folder: str) -> None:
    """Create a Makefile for easy proto generation"""
    makefile_content = f"""# Generated Makefile for Proto to Python generation
# Usage: make proto

PROTO_FOLDER = {proto_folder}
OUTPUT_FOLDER = {output_folder}
PYTHON = python3

.PHONY: proto clean proto-help

proto: generate_proto.py
	$(PYTHON) generate_proto.py $(PROTO_FOLDER) $(OUTPUT_FOLDER)

clean:
	$(PYTHON) generate_proto.py $(PROTO_FOLDER) $(OUTPUT_FOLDER) --clean

proto-help:
	$(PYTHON) generate_proto.py --help

# Auto-detect proto files and generate
proto-auto:
	@echo "Scanning for .proto files in $(PROTO_FOLDER)..."
	@if [ -d "$(PROTO_FOLDER)" ]; then \\
		echo "Found proto files:"; \\
		ls -la $(PROTO_FOLDER)/*.proto 2>/dev/null || echo "No .proto files found"; \\
	else \\
		echo "Proto folder $(PROTO_FOLDER) not found"; \\
	fi

# Install dependencies (Ubuntu/Debian)
install-deps:
	sudo apt-get update
	sudo apt-get install -y protobuf-compiler

# Install dependencies (macOS)
install-deps-mac:
	brew install protobuf

# Install dependencies (Python)
install-python-deps:
	pip install protobuf

# Check if protoc is installed
check-protoc:
	@if command -v protoc >/dev/null 2>&1; then \\
		echo "✓ protoc is installed: $$(protoc --version)"; \\
	else \\
		echo "✗ protoc is not installed. Run 'make install-deps' or 'make install-deps-mac'"; \\
	fi
"""

    makefile_path = Path(output_folder) / "Makefile"
    with open(makefile_path, "w") as f:
        f.write(makefile_content)

    print(f"Created Makefile: {makefile_path}")


def create_init_file(output_folder: str) -> None:
    """Create __init__.py file to make the output folder a Python package"""
    init_path = Path(output_folder) / "__init__.py"
    if not init_path.exists():
        init_content = """# Generated protobuf package
# This file makes the directory a Python package
"""
        with open(init_path, "w") as f:
            f.write(init_content)
        print(f"Created __init__.py: {init_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Python protobuf files from .proto files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./protos
  %(prog)s ./protos ./generated
  %(prog)s ./protos --clean
  %(prog)s ./protos --verbose
        """,
    )

    parser.add_argument("proto_folder", help="Folder containing .proto files")
    parser.add_argument(
        "output_folder",
        nargs="?",
        default="./generated",
        help="Output folder for generated Python files (default: ./generated)",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean generated files before generating"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--no-makefile", action="store_true", help="Skip creating Makefile"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check if protoc is available and list proto files",
    )

    args = parser.parse_args()

    # Check if protoc is installed
    if not check_protoc_installed():
        print("Error: protoc compiler is not installed or not in PATH")
        print("Install it with:")
        print("  Ubuntu/Debian: sudo apt-get install protobuf-compiler")
        print("  macOS: brew install protobuf")
        print(
            "  Windows: Download from https://github.com/protocolbuffers/protobuf/releases"
        )
        sys.exit(1)

    if args.verbose:
        print(f"✓ protoc is available")

    try:
        # Find proto files
        proto_files = find_proto_files(args.proto_folder)

        if args.verbose:
            print(f"Found {len(proto_files)} proto file(s):")
            for proto_file in proto_files:
                print(f"  - {proto_file}")

        if args.check_only:
            print(f"Proto files found: {len(proto_files)}")
            return

        # Clean if requested
        if args.clean:
            if args.verbose:
                print("Cleaning generated files...")
            clean_generated_files(args.output_folder, args.verbose)

        # Generate Python files
        if args.verbose:
            print(f"Generating Python files in: {args.output_folder}")

        success = generate_python_files(
            proto_files, args.output_folder, args.proto_folder, args.verbose
        )

        if success:
            print(
                f"✓ Successfully generated Python files from {len(proto_files)} proto file(s)"
            )

            # Create Makefile unless disabled
            if not args.no_makefile:
                create_makefile(args.output_folder, args.proto_folder)

            # Create __init__.py
            create_init_file(args.output_folder)

            if args.verbose:
                print(f"Output folder: {args.output_folder}")
                print("Generated files:")
                output_path = Path(args.output_folder)
                for py_file in output_path.glob("*_pb2.py"):
                    print(f"  - {py_file}")
        else:
            print("✗ Some files failed to generate")
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
