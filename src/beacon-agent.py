#!/usr/bin/python3 -u

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil
#

import requests
import json
import time
import logging

from beacon_agent.custom_logging import CustomLogging
from beacon_agent.system_metrics_reader import SystemMetricsReader


class BeaconAgent:
    def __init__(self, config_file="/etc/beacon-agent/config.json"):

        custom_logging = CustomLogging()
        custom_logging.configure_logging()

        with open(config_file, 'r') as file:
            config = json.load(file)

        self.api_url = config['agent']['api_url']
        self.api_key = config['agent']['api_key']
        self.refresh_interval_seconds = config['agent']['refresh_interval_seconds']
        self.notify_threshold_percent = config['agent']['notify_threshold_percent']
        self.system_metrics_reader = SystemMetricsReader(config)
        self.metrics = {}

    def check_threshold(self, metrics):
        most_filled_fs = max(metrics['disk_usage'], key=lambda x: x['used_percent'])
        logging.debug(
            f"Most filled file system is mounted on {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        cpu_threshold = metrics['cpu_load_percent'] > self.notify_threshold_percent
        memory_threshold = metrics['memory_info']['percent']
        disk_threshold = most_filled_fs['used_percent']

        if cpu_threshold > self.notify_threshold_percent:
            logging.warning(f"CPU threshold reached at {cpu_threshold}%")
        if memory_threshold > self.notify_threshold_percent:
            logging.warning(f"Memory threshold reached at {memory_threshold}%")
        if disk_threshold > self.notify_threshold_percent:
            logging.warning(
                f"Disk threshold reached at {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        return (cpu_threshold > self.notify_threshold_percent or
                memory_threshold > self.notify_threshold_percent or
                disk_threshold > self.notify_threshold_percent)

    def monitor_system(self):
        logging.info(f"Beacon-Agent started and refreshing system state every {self.refresh_interval_seconds}s")

        # Send metrics once on startup
        self.metrics = self.system_metrics_reader.get_system_metrics()
        self.send_metrics(self.metrics)
        logging.info(f"Initial system state sent.")

        while True:
            start = time.time()
            metrics = self.system_metrics_reader.get_system_metrics()
            took = time.time() - start
            logging.info(f"Metrics refresh took {took:.3f}s")
            if self.check_threshold(metrics):
                self.send_metrics(metrics)
            time.sleep(self.refresh_interval_seconds)

    def send_metrics(self, metrics):
        logging.info("Data sent successfully:")
        self.pretty_print_metrics(metrics)
        return

        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(self.push_url, data=json.dumps(metrics), headers=headers)
            if response.status_code == 200:
                logging.info("Data sent successfully:")
                self.pretty_print_metrics(metrics)
            else:
                logging.info(f"Failed to send data. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.info(f"Error sending data: {e}")

    @staticmethod
    def pretty_print_metrics(metrics):
        logging.info(json.dumps(metrics, indent=2))


if __name__ == "__main__":

    url = 'https://example.com/metrics'
    agent = BeaconAgent(config_file="../example_config.json")

    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        logging.info("\nMonitoring interrupted. Exiting gracefully...")
