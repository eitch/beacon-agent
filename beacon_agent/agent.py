import json
import logging
import time

import requests

from .agent_config import AgentConfig
from .custom_logging import CustomLogging
from .system_metrics_reader import SystemMetricsReader


class BeaconAgent:
    def __init__(self, config_file):

        custom_logging = CustomLogging()
        custom_logging.configure_logging()

        try:
            with open(config_file, 'r') as file:
                config_json = json.load(file)
            logging.info(f"Read config file: {config_file}")
        except FileNotFoundError as e:
            logging.error(f"Config file does not exist at {config_file}!")
            exit(1)

        self.config = AgentConfig(config_json)

        self.api_url = self.config.get_config_value(['agent', 'api_url'])
        self.api_key = self.config.get_config_value(['agent', 'api_key'])

        self.refresh_interval_seconds = self.config.get_config_value(['agent', 'refresh_interval_seconds'], default=10)
        self.notify_delay_seconds = self.config.get_config_value(['agent', 'notify_delay_minutes'], default=10) * 60
        self.notify_threshold_percent = self.config.get_config_value(['agent', 'notify_threshold_percent'], default=90)
        self.system_metrics_reader = SystemMetricsReader(self.config)
        self.last_notify_time = 0
        self.metrics = {}

        logging.info(
            f"Refreshing metrics every {self.refresh_interval_seconds}s, notifying if a threshold reaches {self.notify_threshold_percent}%, or after {self.notify_delay_seconds}s")

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
            last_notify_delay = time.time() - self.last_notify_time
            if last_notify_delay > self.notify_delay_seconds or self.check_threshold(metrics):
                self.send_metrics(metrics)
            time.sleep(self.refresh_interval_seconds)

    def send_metrics(self, metrics):
        logging.info("Data sent successfully:")
        self.pretty_print_metrics(metrics)
        self.last_notify_time = time.time()
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

        self.last_notify_time = time.time()

    @staticmethod
    def pretty_print_metrics(metrics):
        logging.info(json.dumps(metrics, indent=2))


def main():
    agent = BeaconAgent(config_file='../example_config.json')

    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        logging.info("\nMonitoring interrupted. Exiting gracefully...")


if __name__ == "__main__":
    main()
