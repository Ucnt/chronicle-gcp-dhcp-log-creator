#!/usr/bin/env python3
import argparse

# Create an argument parser
parser = argparse.ArgumentParser(description='')

# Add arguments
parser.add_argument("--log_all_hosts", action="store_true", help="Logs all host DHCP records, not just new+updated ones")
parser.add_argument("--dev", action="store_true", help="Used if you want to test this script on a local machine")

# Compile the arguments
args = parser.parse_args()