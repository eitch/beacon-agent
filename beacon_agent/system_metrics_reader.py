import json
import subprocess
import re
import time
import logging
import shutil

# Try to import psutil and handle ImportError
try:
    import psutil
except ImportError:
    psutil = None

from .docker_reader import DockerReader
from .smartctl_reader import SmartCtlReader
from .system_info_reader import SystemInfoReader
from .proxmox_reader import ProxmoxReader


class SystemMetricsReader:
    def __init__(self, config):
        self.system_info_reader = SystemInfoReader()
        self.docker_reader = DockerReader(config)
        self.smartctl_reader = SmartCtlReader(config)
        self.proxmox_reader = ProxmoxReader(config)
        self.prev_cpu_times = None
        self.sys_info = {}
        self.last_metrics = {}

    @staticmethod
    def get_disk_usage_from_df():
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

    @staticmethod
    def get_cpu_count():
        # Read the /proc/cpuinfo content and parse it to count CPUs
        cpu_count = 0
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('processor'):
                    cpu_count += 1
        return cpu_count

    @staticmethod
    def read_cpu_times():
        with open('/proc/stat', 'r') as f:
            first_line = f.readline()
            # Split the line into components
            cpu_times = list(map(int, first_line.split()[1:]))
        return cpu_times

    def calculate_cpu_load(self):
        prev_cpu_times = self.prev_cpu_times
        if self.prev_cpu_times is None:
            # Get initial CPU times
            prev_cpu_times = self.read_cpu_times()
            time.sleep(1)
        curr_times = self.read_cpu_times()

        # Calculate the difference in times
        idle_time = curr_times[3] - prev_cpu_times[3]  # Idle time
        total_time = sum(curr_times) - sum(prev_cpu_times)  # Total time

        # Calculate CPU load percentage
        cpu_load = (1 - (idle_time / total_time)) * 100
        self.prev_cpu_times = curr_times
        return cpu_load

    # Function to gather metrics from /proc
    def get_sys_info_from_proc(self):

        cpu_count = self.get_cpu_count()
        cpu_load_percent = self.calculate_cpu_load()
        logging.debug(f"cpu_load_percent: {cpu_load_percent}")

        # Get memory information from /proc/meminfo
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        meminfo_dict = {line.split(':')[0]: int(line.split(':')[1].strip().split()[0]) for line in meminfo}

        total_memory = meminfo_dict.get('MemTotal', 0)
        free_memory = meminfo_dict.get('MemFree', 0)
        available_memory = meminfo_dict.get('MemAvailable', 0)
        used_memory = total_memory - available_memory
        memory_percent = (used_memory / total_memory) * 100 if total_memory > 0 else 0

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

        system_info = self.system_info_reader.get_system_info()

        # Get CPU load from /proc/loadavg
        load_avg_1, load_avg_5, load_avg_15 = self.get_load_average()

        # annoyingly long-running:
        security_count, non_security_count = self.count_upgradable_packages()

        # read S.M.A.R.T data for all devices
        smart_data = self.smartctl_reader.read_smartdata_for_all_devices()

        # Fetch all Docker Compose projects
        docker_projects = self.docker_reader.list_projects()

        # Fetch proxmox data
        proxmox_data = self.proxmox_reader.read_proxmox_data()

        elapsed_time = time.time() - start_time
        logging.debug(f"Metrics load took: {elapsed_time:.3f}s")

        self.last_metrics = {
            'system_info': system_info,
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
            'disk_usage': sys_info['disk_usage']
        }

        if smart_data is not None:
            self.last_metrics['smart_monitor_data'] = smart_data
        if docker_projects is not None:
            self.last_metrics['docker_projects'] = docker_projects
        if proxmox_data is not None:
            self.last_metrics['proxmox_data'] = proxmox_data

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
        return 0, 0

    @staticmethod
    def count_upgradable_packages_synopkg():
        if shutil.which("synopkg") is None:
            logging.warning("synopkg command is not available. Can not count upgradeable packages.")
            return 0, 0

        try:
            # Run the command to simulate upgrade and capture the output
            start_time = time.time()
            result = subprocess.run(['synopkg', 'checkupdateall'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
            elapsed_time = time.time() - start_time
            if elapsed_time > 3:
                logging.debug(f"Process took: {elapsed_time:.3f} seconds")

            # Split the output into lines
            data = json.loads(result.stdout)

            # all packages are security packages on Synology
            security_count = len(data)
            non_security_count = 0

            return security_count, non_security_count

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return 0, 0

    @staticmethod
    def count_upgradable_packages_apt():
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
                logging.debug(f"Process took: {elapsed_time:.3f} seconds")

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
