import logging
import shutil
import socket

import requests
import urllib3
import json

from requests import HTTPError


class ProxmoxReader:
    def __init__(self, config):
        self.enabled = config.get_config_value(["proxmox", "enabled"], default=False)
        if not self.enabled:
            return

        token_id = config.get_config_value(["proxmox", "token_id"])
        token_secret = config.get_config_value(["proxmox", "token_secret"])

        if shutil.which('pveversion') is None:
            logging.error("pveversion not found, this is not a Proxmox Node.")
            self.enabled = False
            return

        # we connect to localhost, so TLS won't work, so we need to disable TLS validation
        self.host = '127.0.0.1'
        urllib3.disable_warnings()
        verify_tls = False

        self.base_url = f"https://{self.host}:8006/api2/json"
        self.headers = {
            'Authorization': f'PVEAPIToken={token_id}={token_secret}'
        }
        self.verify_tls = verify_tls
        self.node_name = socket.gethostname()
        self.proxmox_data = {}

        logging.info("Enabled ProxmoxReader")

    def _get_vm_details(self):
        url = f'{self.base_url}/nodes/{self.node_name}/qemu'
        logging.debug(f"Getting qemu details for node {self.node_name}")
        response = requests.get(url, headers=self.headers, verify=self.verify_tls, timeout=(5, 5))
        response.raise_for_status()
        return response.json()['data']

    def _get_container_details(self):
        url = f'{self.base_url}/nodes/{self.node_name}/lxc'
        logging.debug(f"Getting lxc details for node {self.node_name}")
        response = requests.get(url, headers=self.headers, verify=self.verify_tls, timeout=(5, 5))
        response.raise_for_status()
        return response.json()['data']

    def read_proxmox_data(self):
        if not self.enabled:
            return None

        try:
            vms = self._get_vm_details()
            containers = self._get_container_details()
        except HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401 or status_code == 403:
                self.proxmox_data = {"error": f"Unauthorized access: {str(e)}"}
            elif status_code == 404:
                self.proxmox_data = {"error": f"Resource not found: {str(e)}"}
            else:
                logging.error(f"Unexpected HTTP error: {str(e)}")
                logging.exception(e)
                self.proxmox_data = {"error": f"HTTP error occurred: {e}. Server message: {str(e)}"}
            return self.proxmox_data
        except Exception as e:
            if "Name or service not known" in str(e):
                self.proxmox_data = {"error": f"Unknown host: {self.host}"}
            elif "timed out" in str(e):
                self.proxmox_data = {"error": f"Connection to host {self.host} timed out!"}
            elif "Connection refused" in str(e):
                self.proxmox_data = {"error": f"Connection refused to host {self.host}!"}
            else:
                logging.error(f"Unexpected error: {str(e)}")
                logging.exception(e)
                self.proxmox_data = {"error": f"An unexpected error occurred: {str(e)}"}
            return self.proxmox_data

        self.proxmox_data = {
            'name': self.node_name,
            'vms': vms,
            'containers': containers
        }
        return self.proxmox_data

    def get_proxmox_data(self):
        return self.proxmox_data


if __name__ == "__main__":
    from custom_logging import CustomLogging
    from agent_config import AgentConfig
    custom_logging = CustomLogging()
    custom_logging.configure_logging()

    with open('../../example_config.json', 'r') as file:
        config = json.load(file)
    config = AgentConfig(config)

    proxmox = ProxmoxReader(config)
    proxmox_data = proxmox.read_proxmox_data()
    logging.info(f'{json.dumps(proxmox_data, indent=2)}')
