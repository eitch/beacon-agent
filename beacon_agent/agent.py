import json
import logging
import time
from urllib.parse import urlencode, quote

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

        self.api_type = self.config.get_config_value(['agent', 'api_type'])
        self.api_url = self.config.get_config_value(['agent', 'api_url'])
        self.api_key = self.config.get_config_value(['agent', 'api_key'])

        self.refresh_interval_seconds = self.config.get_config_value(['agent', 'refresh_interval_seconds'], default=10)
        self.notify_delay_seconds = self.config.get_config_value(['agent', 'notify_delay_minutes'], default=10) * 60
        self.notify_threshold_percent = self.config.get_config_value(['agent', 'notify_threshold_percent'], default=90)
        self.system_metrics_reader = SystemMetricsReader(self.config)
        self.last_notify_time = 0
        self.previous_threshold_nok = False
        self.metrics = {}
        self.latency = 0

        logging.info(
            f"Refreshing metrics every {self.refresh_interval_seconds}s, notifying if a threshold reaches {self.notify_threshold_percent}%, or after {self.notify_delay_seconds}s")

    @staticmethod
    def has_smart_critical_warning(item):
        key, disk = item
        return "smart_health_status" in disk and disk["smart_health_status"] != 'OK'

    @staticmethod
    def is_container_not_running(item):
        key, containers = item
        running_elements = list(filter(lambda element: element["state"] != "running", containers))
        return running_elements is not None and len(running_elements) > 0

    @staticmethod
    def is_vm_lxc_not_running(vm_lxc):
        return vm_lxc['status'] != "running"

    def monitor_system(self):
        logging.info(f"Beacon-Agent started and refreshing system state every {self.refresh_interval_seconds}s")

        # Send metrics once on startup
        self.metrics = self.system_metrics_reader.get_system_metrics()
        self.send_metrics(self.metrics)
        logging.info(f"Initial system state sent.")

        while True:
            start = time.time()
            metrics = self.system_metrics_reader.get_system_metrics()
            self.latency = time.time() - start
            logging.info(f"Metrics refresh took {self.latency:.3f}s")
            last_notify_delay = time.time() - self.last_notify_time
            threshold_reached = self.threshold_reached(metrics)
            if last_notify_delay > self.notify_delay_seconds or threshold_reached or (
                    not threshold_reached and self.previous_threshold_nok):
                self.previous_threshold_nok = threshold_reached
                self.send_metrics(metrics)
            time.sleep(self.refresh_interval_seconds)

    def threshold_reached(self, metrics: object) -> bool:
        cpu_threshold = metrics['cpu_load_percent'] > self.notify_threshold_percent
        memory_threshold = metrics['memory_info']['percent']

        most_filled_fs = max(metrics['disk_usage'], key=lambda x: x['used_percent'])
        disk_threshold = most_filled_fs['used_percent']
        logging.debug(
            f"Most filled file system is mounted on {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        disks_with_critical_warnings = dict(
            filter(self.has_smart_critical_warning, metrics['smart_monitor_data'].items()))
        if disks_with_critical_warnings:
            logging.warning(
                f"The following disks have a critical warning: {', '.join(disks_with_critical_warnings.keys())}")

        containers_not_running = []
        if 'docker_projects' in metrics:
            containers_not_running = dict(
                filter(self.is_container_not_running, metrics['docker_projects'].items()))
            if containers_not_running:
                logging.warning(
                    f"The following containers are not running: {', '.join(containers_not_running.keys())}")

        vms_not_running = []
        lxc_not_running = []
        if 'proxmox_data' in metrics:
            proxmox_data = metrics["proxmox_data"]

            if 'vms' in proxmox_data:
                vms_not_running = dict(
                    filter(self.is_vm_lxc_not_running, proxmox_data['vms']))
                if vms_not_running:
                    logging.warning(
                        f"The following VMs are not running: {', '.join(vms_not_running.keys())}")

            if 'containers' in proxmox_data:
                lxc_not_running = dict(
                    filter(self.is_vm_lxc_not_running, proxmox_data['containers']))
                if lxc_not_running:
                    logging.warning(
                        f"The following LXCs are not running: {', '.join(lxc_not_running.keys())}")

        if cpu_threshold > self.notify_threshold_percent:
            logging.warning(f"CPU threshold reached at {cpu_threshold}%")
        if memory_threshold > self.notify_threshold_percent:
            logging.warning(f"Memory threshold reached at {memory_threshold}%")
        if disk_threshold > self.notify_threshold_percent:
            logging.warning(
                f"Disk threshold reached at {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        security_upgrade_count = metrics["package_security_upgrade_count"]
        if security_upgrade_count > 0:
            logging.warning(f"{security_upgrade_count} security package require upgrading!")

        return (cpu_threshold > self.notify_threshold_percent or
                memory_threshold > self.notify_threshold_percent or
                disk_threshold > self.notify_threshold_percent or
                security_upgrade_count > 0 or
                disks_with_critical_warnings or
                containers_not_running or
                vms_not_running or lxc_not_running)

    def send_metrics(self, metrics):
        match self.api_type:
            case 'Simulated':
                self.send_simulated(metrics)
            case 'UptimeKuma':
                self.send_to_uptime_kuma(metrics)
            case _:
                logging.error("Unknown api_type! Sending simulated!")
                self.send_simulated(metrics)

        self.last_notify_time = time.time()

    def send_simulated(self, metrics):
        logging.info("Doing a simulated send of:")
        self.pretty_print_metrics(metrics)
        logging.info("Successful simulated send")

    def send_to_uptime_kuma(self, metrics):

        # extract what we need for UptimeKuma:
        status = "up"
        kuma_text = ""

        cpu_threshold = metrics['cpu_load_percent'] > self.notify_threshold_percent
        memory_threshold = metrics['memory_info']['percent']
        most_filled_fs = max(metrics['disk_usage'], key=lambda x: x['used_percent'])
        disk_threshold = most_filled_fs['used_percent']
        if cpu_threshold > self.notify_threshold_percent:
            status = "down"
            kuma_text += f"CPU threshold reached at {cpu_threshold}%. "
        if memory_threshold > self.notify_threshold_percent:
            status = "down"
            kuma_text += f"Memory threshold reached at {memory_threshold}%. "
        if disk_threshold > self.notify_threshold_percent:
            status = "down"
            kuma_text += f"Disk threshold reached at {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used. "

        if status == "up":
            kuma_text += "CPU, RAM and Disks OK. "

        security_upgrade_count = metrics["package_security_upgrade_count"]
        if security_upgrade_count == 0:
            kuma_text += "No security package require upgrading. "
        else:
            status = "down"
            kuma_text += f"{security_upgrade_count} security package require upgrading! "

        disks_with_critical_warnings = dict(
            filter(self.has_smart_critical_warning, metrics['smart_monitor_data'].items()))
        if len(disks_with_critical_warnings) == 0:
            kuma_text += "All disks OK. "
        else:
            status = "down"
            for item in disks_with_critical_warnings.items():
                label, disk = item
                kuma_text += f"Disk {label} FAILED. "

        containers_not_running = []
        if 'docker_projects' in metrics:
            containers_not_running = dict(
                filter(self.is_container_not_running, metrics['docker_projects'].items()))
            if len(containers_not_running) == 0:
                kuma_text += "All containers running. "
            else:
                status = "down"
                for item in containers_not_running.items():
                    label, containers = item
                    stopped_containers = list(filter(lambda element: element["state"] != "running", containers))
                    for container in stopped_containers:
                        kuma_text += f"Container {label}:{container['name']} state={container['state']}. "

        if "proxmox_data" in metrics:
            proxmox_data = metrics["proxmox_data"]
            if 'vms' in proxmox_data:
                vms_not_running = dict(
                    filter(self.is_vm_lxc_not_running, proxmox_data['vms']))
                if len(vms_not_running) == 0:
                    kuma_text += "All VMs running. "
                else:
                    status = "down"
                    for vm in vms_not_running:
                        kuma_text += f"VM {vm['name']} state={vm['status']}. "

            if 'containers' in proxmox_data:
                lxc_not_running = dict(
                    filter(self.is_vm_lxc_not_running, proxmox_data['containers']))
                if len(lxc_not_running) == 0:
                    kuma_text += "All LXCs running. "
                else:
                    status = "down"
                    for lxc in lxc_not_running:
                        kuma_text += f"LXC {lxc_not_running['name']} state={lxc_not_running['status']}. "

        encoded = quote(kuma_text)
        url = f"{self.api_url}/{self.api_key}?status={status}&msg={encoded}&ping={self.latency}"
        logging.info(f"Sending to UptimeKuma at URL {url}")
        try:
            response = requests.get(url, data=json.dumps(metrics))
            if response.status_code == 200:
                logging.info("Data sent successfully to UptimeKuma")
            else:
                logging.info(f"Failed to send data. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.info(f"Error sending data: {e}")

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
