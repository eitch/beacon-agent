#!/usr/bin/python3

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil python3-docker
#

import requests
import json
import time
import logging

from lib.system_metrics_reader import SystemMetricsReader


class BeaconAgent:
    def __init__(self, push_url, interval=10, threshold=90):
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s.%(msecs)03d %(module)s %(levelname)s:\t%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S'
                            )
        self.push_url = push_url
        self.interval = interval
        self.threshold = threshold
        self.log = logging.getLogger(__name__)
        self.system_metrics_reader = SystemMetricsReader()
        self.metrics = {}
        self.log.info("Started Beacon-Agent")

    def check_threshold(self, metrics):
        return (metrics['cpu_load_percent'] > self.threshold or
                metrics['memory']['percent'] > self.threshold or
                metrics['disk']['percent'] > self.threshold)

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
        self.log.info("Data sent successfully:")
        self.pretty_print_metrics(metrics)
        return
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(self.push_url, data=json.dumps(metrics), headers=headers)
            if response.status_code == 200:
                self.log.info("Data sent successfully:")
                self.pretty_print_metrics(metrics)
            else:
                self.log.info(f"Failed to send data. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.log.info(f"Error sending data: {e}")

    @staticmethod
    def pretty_print_metrics(metrics):
        logging.info(json.dumps(metrics, indent=4))


if __name__ == "__main__":

    url = 'https://example.com/metrics'
    agent = BeaconAgent(url, interval=10, threshold=90)

    log = logging.getLogger(__name__)
    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        log.info("\nMonitoring interrupted. Exiting gracefully...")
