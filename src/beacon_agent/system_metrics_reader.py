#!/usr/bin/python3

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil python3-docker
#

import subprocess
import re
import psutil
import time
import logging

from .docker_compose_reader import DockerComposeReader
from .smartctl_reader import SmartCtlReader


class SystemMetricsReader:
    def __init__(self):
        self.docker_compose_reader = DockerComposeReader()
        self.smartctl_reader = SmartCtlReader()
        self.last_metrics = {}

    def get_system_metrics(self):
        start_time = time.time()

        cpu_load_percent = psutil.cpu_percent(interval=1)
        num_cpu_cores = psutil.cpu_count(logical=True)
        max_cpu_load_percent = 100 * num_cpu_cores  # 100% load per core
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')

        # Get CPU load from /proc/loadavg
        load_avg_1, load_avg_5, load_avg_15 = self.get_load_average()

        # annoyingly long-running:
        security_count, non_security_count = self.count_upgradable_packages()

        # read S.M.A.R.T data for all devices
        smart_data = self.smartctl_reader.read_smartdata_for_all_devices()

        # Fetch all Docker Compose projects
        projects = self.docker_compose_reader.list_compose_projects()

        elapsed_time = time.time() - start_time
        logging.info(f"Metrics load took: {elapsed_time:.3f} seconds")

        self.last_metrics = {
            'num_cpu_cores': num_cpu_cores,
            'cpu_load_percent': cpu_load_percent,
            'max_cpu_load_percent': max_cpu_load_percent,
            'load_avg': {
                '1_min': load_avg_1,
                '5_min': load_avg_5,
                '15_min': load_avg_15
            },
            'memory': {
                'total': memory_info.total,
                'used': memory_info.used,
                'free': memory_info.free,
                'percent': memory_info.percent
            },
            'disk': {
                'total': disk_usage.total,
                'used': disk_usage.used,
                'free': disk_usage.free,
                'percent': disk_usage.percent
            },
            'package_upgrade_count': non_security_count + security_count,
            'package_security_upgrade_count': security_count,
            'smart_monitor_data': smart_data,
            'docker_compose_projects': projects
        }

        return self.last_metrics

    @staticmethod
    def get_load_average():
        with open('/proc/loadavg', 'r') as f:
            load_avg = f.read().strip().split()
            load_avg_1 = float(load_avg[0])  # Load average for the last 1 minute
            load_avg_5 = float(load_avg[1])  # Load average for the last 5 minutes
            load_avg_15 = float(load_avg[2])  # Load average for the last 15 minutes
        return load_avg_1, load_avg_5, load_avg_15

    def count_upgradable_packages(self):
        try:
            # Run the command to simulate upgrade and capture the output
            start_time = time.time()
            result = subprocess.run(
                ['apt-get', '--just-print', 'dist-upgrade'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            elapsed_time = time.time() - start_time
            if elapsed_time > 3:
                logging.info(f"Process took: {elapsed_time:.3f} seconds")

            # Split the output into lines
            lines = result.stdout.strip().split('\n')

            # Initialize counts
            security_count = 0
            non_security_count = 0

            # Regular expression to match package lines
            package_regex = re.compile(r'^\s*Inst\s+.*')

            for line in lines:
                match = package_regex.match(line)
                if match:
                    # Check if the package has a security upgrade available
                    if 'security' in line:
                        security_count += 1
                    else:
                        non_security_count += 1

            return security_count, non_security_count

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return None, None
