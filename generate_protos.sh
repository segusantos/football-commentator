#!/bin/bash

# Ensure the script exits on any error
set -e

# Define source and output directories
PROTO_SOURCE_DIR="./protos"
COMMENTARY_GENERATED_DIR="./commentary/generated"
TTS_GENERATED_DIR="./tts/generated"

# Clean up old generated files (optional, but good practice)
rm -rf "${COMMENTARY_GENERATED_DIR}"
rm -rf "${TTS_GENERATED_DIR}"

# Create output directories if they don't exist
mkdir -p "${COMMENTARY_GENERATED_DIR}"
mkdir -p "${TTS_GENERATED_DIR}"

# Generate gRPC stubs for Python for commentary service
echo "Generating gRPC stubs for Commentary service..."
python -m grpc_tools.protoc \
    -I"${PROTO_SOURCE_DIR}" \
    --python_out="${COMMENTARY_GENERATED_DIR}" \
    --grpc_python_out="${COMMENTARY_GENERATED_DIR}" \
    "${PROTO_SOURCE_DIR}/game_event.proto" \
    "${PROTO_SOURCE_DIR}/commentary_to_tts.proto"

# Generate gRPC stubs for Python for tts service
echo "Generating gRPC stubs for TTS service..."
python -m grpc_tools.protoc \
    -I"${PROTO_SOURCE_DIR}" \
    --python_out="${TTS_GENERATED_DIR}" \
    --grpc_python_out="${TTS_GENERATED_DIR}" \
    "${PROTO_SOURCE_DIR}/commentary_to_tts.proto"

# Create __init__.py files to make the generated directories Python packages
echo "Creating __init__.py files..."
touch "${COMMENTARY_GENERATED_DIR}/__init__.py"
touch "${TTS_GENERATED_DIR}/__init__.py"

echo "Protocol buffer compilation complete."
echo "Generated files are in ${COMMENTARY_GENERATED_DIR} and ${TTS_GENERATED_DIR}" 