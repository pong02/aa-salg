#!/bin/bash

echo "Running generateLabels.py..."
python3 generateLabels.py

if [ $? -ne 0 ]; then
    echo "Error running generateLabels.py. Exiting..."
    read -p "Press any key to exit..." -n1 -s
    exit 1
fi

echo "Running merge.py..."
python3 merge.py

if [ $? -ne 0 ]; then
    echo "Error running merge.py. Exiting..."
    read -p "Press any key to exit..." -n1 -s
    exit 1
fi

echo "All scripts executed successfully!"
read -p "Press any key to exit..." -n1 -s
