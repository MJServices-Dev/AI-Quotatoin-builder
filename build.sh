#!/bin/bash
set -e

echo "Installing dependencies without pycairo chain..."

# Install most packages normally
uv pip install --system -r requirements.txt --no-deps

# Install xhtml2pdf + svglib carefully
uv pip install --system xhtml2pdf==0.2.17 "svglib<1.6.0"

# Re-install any other specific packages that need deps
uv pip install --system -r requirements.txt
