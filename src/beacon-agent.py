#!/usr/bin/python3

#
# Prerequisites
#
#   sudo apt install python3-requests python3-psutil python3-docker
#

import subprocess
import re
import psutil
import requests
import json
import time
import logging
from lib.docker_compose_manager import DockerComposeManager

# Create an instance of the DockerComposeManager
docker_manager = DockerComposeManager()

# Function to gather system metrics
def get_system_metrics():
    cpu_load_percent = psutil.cpu_percent(interval=1)
    num_cpu_cores = psutil.cpu_count(logical=True)
    max_cpu_load_percent = 100 * num_cpu_cores  # 100% load per core
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    # Get CPU load from /proc/loadavg
    load_avg_1, load_avg_5, load_avg_15 = get_load_average()

    security_count, non_security_count = count_upgradable_packages()

    metrics = {
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
        'package_security_upgrade_count': security_count
    }

    return metrics


# Function to get CPU load averages from /proc/loadavg
def get_load_average():
    with open('/proc/loadavg', 'r') as f:
        load_avg = f.read().strip().split()
        load_avg_1 = float(load_avg[0])  # Load average for the last 1 minute
        load_avg_5 = float(load_avg[1])  # Load average for the last 5 minutes
        load_avg_15 = float(load_avg[2])  # Load average for the last 15 minutes
    return load_avg_1, load_avg_5, load_avg_15


def count_upgradable_packages():
    try:
        # Run the command to simulate upgrade and capture the output
        result = subprocess.run(
            ['apt-get', '--just-print', 'upgrade'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Split the output into lines
        lines = result.stdout.strip().split('\n')

        # Initialize counts
        security_count = 0
        non_security_count = 0

        # Regular expression to match package lines
        package_regex = re.compile(r'^\s*Inst\s+(^\s+)\s+\[.*\]')

        for line in lines:
            match = package_regex.match(line)
            if match:
                # Check if the package has a security upgrade available
                # This will generally require knowledge of the package's source
                # Here we are only counting based on the output format
                if 'security' in line:
                    security_count += 1
                else:
                    non_security_count += 1

        return security_count, non_security_count

    except Exception as e:
        log.info(f"An error occurred: {e}")
        return None, None


# Function to check if any metric exceeds 90% capacity
def check_threshold(metrics, threshold=90):
    return (metrics['cpu_load_percent'] > threshold or
            metrics['memory']['percent'] > threshold or
            metrics['disk']['percent'] > threshold)


# Main function to send data on startup and only when thresholds are exceeded
def monitor_system(interval=10, threshold=90):
    # Send metrics once on startup
    metrics = get_system_metrics()
    send_metrics(metrics)

    docker_manager.print_project_details()

    while True:
        metrics = get_system_metrics()
        if check_threshold(metrics, threshold):
            send_metrics(metrics)
        time.sleep(interval)


# Function to send the data to the specified URL
def send_metrics(metrics):
    log.info("Data sent successfully:")
    pretty_print_metrics(metrics)
    return
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(push_url, data=json.dumps(metrics), headers=headers)
        if response.status_co0de == 200:
            log.info("Data sent successfully:")
            pretty_print_metrics(metrics)
        else:
            log.info(f"Failed to send data. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log.info(f"Error sending data: {e}")


# Function to pretty print the metrics
def pretty_print_metrics(metrics):
    log.info(json.dumps(metrics, indent=4))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s.%(msecs)03d %(module)s %(levelname)s:\t%(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                        )
    log = logging.getLogger(__name__)
    log.info("Started Beacon-Agent")

    # Replace with your URL
    push_url = 'https://example.com/metrics'

    try:
        # Monitor every 10 seconds but only send when usage > 90%
        monitor_system(interval=10, threshold=90)
    except KeyboardInterrupt:
        log.info("\nMonitoring interrupted. Exiting gracefully...")
