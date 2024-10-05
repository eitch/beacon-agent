#!/usr/bin/python3 -u

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil
#

import argparse
import logging

from beacon_agent.agent import BeaconAgent


def main():
    parser = argparse.ArgumentParser(description="Specify config file using -f")
    parser.add_argument('-f', '--file', type=str, default='/etc/beacon-agen/config.json',
                        help='Path to the config file')
    args = parser.parse_args()

    config_file = args.file
    agent = BeaconAgent(config_file=config_file)

    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        logging.info("\nMonitoring interrupted. Exiting gracefully...")


if __name__ == "__main__":
    main()
