#!/usr/bin/python3
import shutil
#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil python3-docker
#

import subprocess
import re
import time
import logging

# Try to import psutil and handle ImportError
try:
    import psutil
except ImportError:
    psutil = None

from .docker_compose_reader import DockerComposeReader
from .smartctl_reader import SmartCtlReader


class SystemMetricsReader:
    def __init__(self):
        self.docker_compose_reader = DockerComposeReader()
        self.smartctl_reader = SmartCtlReader()
        self.sys_info = {}
        self.last_metrics = {}

    def get_disk_usage_from_df(self):
        # Execute the command
        result = subprocess.run(
            ['df', '-l', '-x', 'overlay', '-x', 'tmpfs', '-x', 'efivarf', '-x', 'devtmpfs', '-x', 'none'],
            stdout=subprocess.PIPE, text=True)

        # Split the output into lines
        lines = result.stdout.strip().split('\n')

        # Initialize a list to hold the dictionary entries
        df_dict = []

        # Iterate over the remaining lines and parse each line
        for line in lines[1:]:
            values = line.split()

            if values[0] in ['overlay', 'tmpfs', 'efivarfs', 'devtmpfs', 'none']:
                continue

            df_entry = {
                'file_system': values[0],
                'used': int(values[2]),
                'available': int(values[3]),
                'used_percent': int(values[4].rstrip('%')),
                'mount_point': values[5]
            }

            df_dict.append(df_entry)

        return df_dict

    # Function to gather metrics from /proc
    def get_sys_info_from_proc(self):

        cpu_load_percent = 0
        cpu_count = 0

        # Get memory information from /proc/meminfo
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        meminfo_dict = {line.split(':')[0]: int(line.split(':')[1].strip().split()[0]) for line in meminfo}

        total_memory = meminfo_dict.get('MemTotal', 0)
        free_memory = meminfo_dict.get('MemFree', 0)
        available_memory = meminfo_dict.get('MemAvailable', 0)
        used_memory = total_memory - available_memory
        memory_percent = (used_memory / total_memory) * 100 if total_memory > 0 else 0

        # # Get disk usage from /proc/diskstats (simplified)
        # with open('/proc/diskstats', 'r') as f:
        #     disk_usage = f.readlines()
        # total_disk = sum(int(line.split()[3]) for line in disk_usage)  # Assuming first entry for simplicity
        # used_disk = 0  # This requires more complex logic or additional data
        # free_disk = total_disk - used_disk if total_disk > 0 else 0
        # disk_percent = (used_disk / total_disk) * 100 if total_disk > 0 else 0

        disk_usage = self.get_disk_usage_from_df()

        return {
            'cpu_load_percent': cpu_load_percent,
            'num_cpu_cores': cpu_count,
            'max_cpu_load_percent': 100 * cpu_count,
            'memory_info': {
                'total': total_memory,
                'used': used_memory,
                'free': free_memory,
                'available': available_memory,
                'percent': memory_percent
            },
            'disk_usage': disk_usage,
        }

    def get_sys_info_from_psutil(self):
        cpu_count = psutil.cpu_count(logical=True)
        memory = psutil.virtual_memory()

        # TODO handle: psutil.disk_partitions
        # disk_usage = psutil.disk_usage('/')

        disk_usage = self.get_disk_usage_from_df()

        return {
            'cpu_load_percent': psutil.cpu_percent(interval=1),
            'num_cpu_cores': cpu_count,
            'max_cpu_load_percent': 100 * cpu_count,
            'memory_info': {
                'total': memory.total,
                'used': memory.used,
                'free': memory.free,
                'available': memory.available,
                'percent': memory.percent
            },
            'disk_usage': disk_usage,
        }

    def read_sys_info(self):
        if psutil is None:
            self.sys_info = self.get_sys_info_from_proc()
        else:
            self.sys_info = self.get_sys_info_from_psutil()
        return self.sys_info

    def get_system_metrics(self):
        start_time = time.time()

        # read the system info
        sys_info = self.read_sys_info()

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
            'num_cpu_cores': sys_info['num_cpu_cores'],
            'cpu_load_percent': sys_info['cpu_load_percent'],
            'max_cpu_load_percent': sys_info['max_cpu_load_percent'],
            'load_avg': {
                '1_min': load_avg_1,
                '5_min': load_avg_5,
                '15_min': load_avg_15
            },
            'package_upgrade_count': non_security_count + security_count,
            'package_security_upgrade_count': security_count,
            'memory_info': sys_info['memory_info'],
            'disk_usage': sys_info['disk_usage'],
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
        if shutil.which("apt-get") is not None:
            return self.count_upgradable_packages_apt()
        if shutil.which("synopkg") is not None:
            return self.count_upgradable_packages_synopkg()

    def count_upgradable_packages_synopkg(self):
        if shutil.which("synopkg") is None:
            logging.warning("synopkg command is not available. Can not count upgradeable packages.")
            return 0, 0

        try:
            # Run the command to simulate upgrade and capture the output
            start_time = time.time()
            result = subprocess.run(['synopkg', 'chkupgradepkg'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
            elapsed_time = time.time() - start_time
            if elapsed_time > 3:
                logging.info(f"Process took: {elapsed_time:.3f} seconds")

            # Split the output into lines
            lines = result.stdout.strip().split('\n')

            # Initialize counts
            security_count = 0
            non_security_count = 0

            for line in lines:
                if '->' in line:
                    security_count += 1

            return security_count, non_security_count

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return 0, 0

    def count_upgradable_packages_apt(self):
        if shutil.which("apt-get") is None:
            logging.warning("apt-get command is not available. Can not count upgradeable packages.")
            return 0, 0

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
            return 0, 0
