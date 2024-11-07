import json
import logging
import time

import requests

from beacon_agent import AGENT_VERSION
from .agent_config import AgentConfig
from .custom_logging import CustomLogging
from .system_metrics_reader import SystemMetricsReader


class BeaconAgent:
    def __init__(self, config_file):

        custom_logging = CustomLogging()
        custom_logging.configure_logging()

        logging.info(f"Initializing Beacon Agent {AGENT_VERSION} with config file {config_file}")

        try:
            with open(config_file, 'r') as file:
                config_json = json.load(file)
            logging.info(f"Read config file: {config_file}")
        except FileNotFoundError:
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

    def _read_metrics(self):
        start = time.time()
        self.metrics = self.system_metrics_reader.get_system_metrics()
        self.metrics["version"] = AGENT_VERSION
        self.latency = round(time.time() - start, 3)
        logging.info(f"Metrics refresh took {self.latency}s")

    def monitor_system(self):
        logging.info(f"Beacon-Agent started and refreshing system state every {self.refresh_interval_seconds}s")

        # Send metrics once on startup
        self._read_metrics()
        self.send_metrics()
        logging.info(f"Initial system state sent.")

        while True:
            self._read_metrics()

            last_notify_delay = time.time() - self.last_notify_time
            threshold_reached, error_msg = self._threshold_reached()
            if error_msg or last_notify_delay > self.notify_delay_seconds or threshold_reached or (
                    not threshold_reached and self.previous_threshold_nok):
                self.previous_threshold_nok = threshold_reached
                self.send_metrics(error_msg)
            time.sleep(self.refresh_interval_seconds)

    def _threshold_reached(self) -> tuple[bool, list]:
        cpu_threshold = self.metrics['cpu_load_percent'] > self.notify_threshold_percent
        memory_threshold = self.metrics['memory_info']['percent']

        most_filled_fs = max(self.metrics['disk_usage'], key=lambda x: x['used_percent'])
        disk_threshold = most_filled_fs['used_percent']
        logging.debug(
            f"Most filled file system is mounted on {most_filled_fs['mount_point']} at {most_filled_fs['used_percent']}% used")

        error_msg = []

        disks_with_critical_warnings = []
        if 'smart_monitor_data' in self.metrics:
            data = self.metrics['smart_monitor_data']
            if 'error' in data:
                error_msg.append(data['error'])
            disks_with_critical_warnings = dict(
                filter(self.has_smart_critical_warning, data.items()))
            if disks_with_critical_warnings:
                logging.warning(
                    f"The following disks have a critical warning: {', '.join(disks_with_critical_warnings.keys())}")

        missing_disks = None
        if 'missing_disks' in self.metrics:
            missing_disks = self.metrics['missing_disks']
            logging.error(f"The following disks are missing: {json.dumps(missing_disks)}")

        containers_not_running = []
        if 'docker_projects' in self.metrics:
            containers_not_running = dict(
                filter(self.is_container_not_running, self.metrics['docker_projects'].items()))
            if containers_not_running:
                logging.warning(
                    f"The following containers are not running: {', '.join(containers_not_running.keys())}")

        vms_not_running = []
        lxc_not_running = []
        if 'proxmox_data' in self.metrics:
            proxmox_data = self.metrics["proxmox_data"]
            if 'error' in proxmox_data:
                error_msg.append(proxmox_data['error'])

            if 'vms' in proxmox_data:
                vms_not_running = {vm['name']: vm for vm in proxmox_data['vms'] if self.is_vm_lxc_not_running(vm)}
                if vms_not_running:
                    logging.warning(
                        f"The following VMs are not running: {', '.join(vms_not_running.keys())}")

            if 'containers' in proxmox_data:
                lxc_not_running = {lxc['name']: lxc for lxc in proxmox_data['containers'] if
                                   self.is_vm_lxc_not_running(lxc)}
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

        security_upgrade_count = self.metrics["package_security_upgrade_count"]
        if security_upgrade_count > 0:
            logging.warning(f"{security_upgrade_count} security package require upgrading!")

        return (cpu_threshold > self.notify_threshold_percent or
                memory_threshold > self.notify_threshold_percent or
                disk_threshold > self.notify_threshold_percent or
                security_upgrade_count > 0 or
                disks_with_critical_warnings or missing_disks or
                containers_not_running or
                vms_not_running or lxc_not_running), error_msg

    def send_metrics(self, error_msg=None):
        if self.api_type == 'Simulated':
            self._send_simulated(error_msg)
        elif self.api_type == 'UptimeKuma':
            self._send_to_uptime_kuma(error_msg)
        else:
            logging.error("Unknown api_type! Sending simulated!")
            self._send_simulated(error_msg)
        self.last_notify_time = time.time()

    def _send_simulated(self, error_msg=None):
        logging.info("Doing a simulated send of:")
        self._pretty_print_metrics(error_msg)
        logging.info("Successful simulated send")

    def _send_to_uptime_kuma(self, error_msg=None):
        metrics = self.metrics

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

        if 'package_security_upgrade_count' in metrics:
            security_upgrade_count = metrics["package_security_upgrade_count"]
            if security_upgrade_count == 0:
                kuma_text += "No security package require upgrading. "
            else:
                status = "down"
                kuma_text += f"{security_upgrade_count} security package require upgrading! "

        missing_disks = None
        if 'missing_disks' in self.metrics:
            missing_disks = self.metrics['missing_disks']
            status = "down"
            kuma_text += f"Missing disks: {json.dumps(missing_disks)}. "
        if 'smart_monitor_data' in metrics:
            disks_with_critical_warnings = dict(
                filter(self.has_smart_critical_warning, metrics['smart_monitor_data'].items()))
            if len(disks_with_critical_warnings) == 0 and missing_disks is None:
                kuma_text += "All disks OK. "
            else:
                status = "down"
                for item in disks_with_critical_warnings.items():
                    label, disk = item
                    kuma_text += f"Disk {label} FAILED. "

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
                vms_not_running = {vm['name']: vm for vm in proxmox_data['vms'] if self.is_vm_lxc_not_running(vm)}
                if len(vms_not_running) == 0:
                    kuma_text += "All VMs running. "
                else:
                    status = "down"
                    for item in vms_not_running.items():
                        label, vm = item
                        kuma_text += f"VM {label} state={vm['status']}. "

            if 'containers' in proxmox_data:
                lxc_not_running = {lxc['name']: lxc for lxc in proxmox_data['containers'] if
                                   self.is_vm_lxc_not_running(lxc)}
                if len(lxc_not_running) == 0:
                    kuma_text += "All LXCs running. "
                else:
                    status = "down"
                    for item in lxc_not_running.items():
                        label, lxc = item
                        kuma_text += f"LXC {label} state={lxc['status']}. "

        if error_msg:
            status = "down"
            kuma_text += f"ERROR_MSG:{error_msg}. "

        kuma_text += f"Agent:{AGENT_VERSION}. "

        url = f"{self.api_url}/{self.api_key}"
        logging.info(f"Sending status {status} to UptimeKuma at URL {self.api_url}")
        logging.info(f"Kuma message: {kuma_text}")
        try:
            response = requests.get(url, {"status": status, "msg": kuma_text, "ping": self.latency})
            if response.status_code == 200:
                logging.info("Data sent successfully to UptimeKuma")
            else:
                logging.info(f"Failed to send data. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.info(f"Error sending data: {e}")

    def _pretty_print_metrics(self, error_msg=None):
        logging.info(json.dumps(self.metrics, indent=2))
        if error_msg:
            logging.info(f"Error message: {error_msg}")


def main():
    agent = BeaconAgent(config_file='../example_config.json')

    try:
        agent.monitor_system()
    except KeyboardInterrupt:
        logging.info("\nMonitoring interrupted. Exiting gracefully...")


if __name__ == "__main__":
    main()
