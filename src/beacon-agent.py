#!/usr/bin/python3 -u

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil python3-docker
#

import requests
import json
import time
import logging

from beacon_agent.system_metrics_reader import SystemMetricsReader


class CustomFormatter(logging.Formatter):
    def __init__(self, fixed_length=20, *args, **kwargs):
        self.fixed_length = fixed_length
        super().__init__(*args, **kwargs)

    def format(self, record):
        # Format the module name to ensure it is exactly fixed_length characters
        record.module = f"{record.module:<{self.fixed_length}}"[
                        :self.fixed_length]  # Pad with spaces and truncate if necessary
        return super().format(record)


class BeaconAgent:
    def __init__(self, push_url, interval=10, threshold=90):
        logger = logging.root
        logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Create custom formatter with a max length of 10 for module names
        formatter = CustomFormatter(datefmt='%Y-%m-%d %H:%M:%S',
                                    fmt='%(asctime)s.%(msecs)03d %(module)s %(levelname)s: %(message)s',
                                    fixed_length=20)
        ch.setFormatter(formatter)

        # Add handler to the logger
        logger.addHandler(ch)
        self.push_url = push_url
        self.interval = interval
        self.threshold = threshold
        self.system_metrics_reader = SystemMetricsReader()
        self.metrics = {}
        logging.info("Started Beacon-Agent")

    def check_threshold(self, metrics):
        most_filled_fs = max(metrics['disk_usage'], key=lambda x: x['used_percent'])
        logging.info(
            f"Most filled file system is mounted on {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        cpu_threshold = metrics['cpu_load_percent'] > self.threshold
        memory_threshold = metrics['memory_info']['percent']
        disk_threshold = most_filled_fs['used_percent']

        if cpu_threshold > self.threshold:
            logging.warning(f"CPU threshold reached at {cpu_threshold}%")
        if memory_threshold > self.threshold:
            logging.warning(f"Memory threshold reached at {memory_threshold}%")
        if disk_threshold > self.threshold:
            logging.warning(
                f"Disk threshold reached at {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        return (cpu_threshold > self.threshold or
                memory_threshold > self.threshold or
                disk_threshold > self.threshold)

    def monitor_system(self):
        # Send metrics once on startup
        self.metrics = self.system_metrics_reader.get_system_metrics()
        self.send_metrics(self.metrics)

        while True:
            metrics = self.system_metrics_reader.get_system_metrics()
            if self.check_threshold(metrics):
                self.send_metrics(metrics)
            time.sleep(self.interval)

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
        logging.info(json.dumps(metrics, indent=4))


if __name__ == "__main__":

    url = 'https://example.com/metrics'
    agent = BeaconAgent(url, interval=10, threshold=90)

    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        logging.info("\nMonitoring interrupted. Exiting gracefully...")
