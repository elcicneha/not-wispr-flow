#!/bin/bash
#
# Stop background Whispr process
#

echo "Stopping Whispr..."

# Find and kill the process
pkill -f whispr_clone.py

if [ $? -eq 0 ]; then
    echo "Whispr stopped successfully"
else
    echo "Whispr is not running"
fi
