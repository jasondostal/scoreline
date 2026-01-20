#!/bin/sh
set -e

# Scoreline entrypoint - populate user config with defaults on first run

CONFIG_DIR="${CONFIG_DIR:-/app/config}"
DEFAULTS_DIR="${DEFAULTS_DIR:-/app/defaults}"

# Create config directory structure if needed
mkdir -p "$CONFIG_DIR/leagues"

# Copy default settings.yaml if missing
if [ ! -f "$CONFIG_DIR/settings.yaml" ]; then
    echo "First run: creating default settings.yaml"
    cp "$DEFAULTS_DIR/settings.yaml" "$CONFIG_DIR/settings.yaml"
fi

# Copy default leagues if leagues directory is empty
if [ -z "$(ls -A "$CONFIG_DIR/leagues" 2>/dev/null)" ]; then
    echo "First run: copying default league definitions"
    cp "$DEFAULTS_DIR/leagues/"*.yaml "$CONFIG_DIR/leagues/"
fi

echo "Config ready at $CONFIG_DIR"

# Hand off to the main command
exec "$@"
