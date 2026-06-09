#!/usr/bin/env bash
set -e

echo "============================================"
echo " Nutrigenomics GraphRAG — Test Runner"
echo "============================================"

echo ""
echo "Running unit tests (no Docker required)..."
pytest -m "not integration" -ra -q
echo "Unit tests complete."

echo ""
echo "Running integration tests (requires Neo4j + Redis via Docker)..."
pytest -m integration -ra -q
echo "Integration tests complete."
