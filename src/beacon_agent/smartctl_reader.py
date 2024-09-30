import subprocess
import logging
import shutil
import glob
import re
import json

class SmartCtlReader:
    def __init__(self):
        """Initialize the DockerComposeReader."""
        self.devices = []
        self.smart_data = {}

    @staticmethod
    def check_smartctl_available():
        """
        Check if smartctl is available on the system.

        Returns:
        bool: True if smartctl is available, False otherwise.
        """
        return shutil.which("smartctl") is not None

    def get_smart_data(self, device):
        """
        Get S.M.A.R.T. data for a given device using the smartctl command.
        Args:
        device (str): The device path, e.g., '/dev/sda'

        Returns:
        dict: Parsed S.M.A.R.T. data or error message if unsuccessful
        """

        logging.info(f"Getting S.M.A.R.T. data for {device}...")
        if not self.check_smartctl_available():
            return {"error": "smartctl command is not available. Please install smartmontools."}

        try:
            # Execute the smartctl command
            result = subprocess.run(['smartctl', '-a', device], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
            if result.returncode != 0:
                return {"error": f"Failed to get S.M.A.R.T data for {device}. Error: {result.stderr}"}

            # Process the output and parse the necessary fields
            output_lines = result.stdout.splitlines()
            smart_data = {'is_nvme': 'false'}

            for line in output_lines:
                # Example parsing logic: collect any lines starting with 'ID#', which typically contains attributes.
                if line.startswith("ID#"):
                    continue  # Skip header line
                if line.strip() == "":
                    continue  # Skip empty lines

                # Example format:
                # ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE
                # 1   Raw_Read_Error_Rate     0x000f   100   100   051    Pre-fail  Always       -       0
                parts = line.split()
                if len(parts) > 9:
                    attr_id = parts[0]
                    attr_name = parts[1]
                    smart_data[attr_name] = {
                        "ID": attr_id,
                        "FLAG": parts[2],
                        "VALUE": parts[3],
                        "WORST": parts[4],
                        "THRESH": parts[5],
                        "TYPE": parts[6],
                        "UPDATED": parts[7],
                        "WHEN_FAILED": parts[8],
                        "RAW_VALUE": parts[9]
                    }

            return smart_data

        except Exception as e:
            return {"error": f"Exception occurred: {str(e)}"}

    @staticmethod
    def get_nvme_status(device):
        """
        Get the S.M.A.R.T. status of an NVMe drive using the nvme tool.

        Args:
        device (str): The NVMe device path (e.g., /dev/nvme0n1).

        Returns:
        dict: A dictionary containing the S.M.A.R.T. status information, or an error message if unsuccessful.
        """
        status = {'is_nvme': 'true'}

        try:
            # Run the nvme smart-log command to get S.M.A.R.T. information
            nvme_output = subprocess.run(['nvme', 'smart-log', device], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True)
            if nvme_output.returncode == 0:
                # Parse the output to extract the S.M.A.R.T. information
                for line in nvme_output.stdout.splitlines():
                    # Example line: "critical_warning: 0"
                    if line:
                        key, value = line.split(':', 1)
                        status[key.strip()] = value.strip()
                return status
            else:
                # Handle permission denied errors gracefully
                if "Permission denied" in nvme_output.stderr:
                    return {"error": f"Permission denied when accessing {device}. Please run as superuser."}
                return {"error": f"Failed to retrieve status for {device}: {nvme_output.stderr.strip()}"}

        except Exception as e:
            return {"error": str(e)}

    def list_devices(self):
        """
        List all potential devices, prioritizing /dev/sata*.
        If none are found, check for /dev/sd*, then /dev/sg*, and finally always include /dev/nvme* devices.

        Returns:
        list: A list of block device paths (e.g., /dev/sata0, /dev/sda, /dev/nvme0n1).
        """
        self.devices = []

        # Regex patterns for filtering
        sata_pattern = re.compile(r'^/dev/sata[0-9]+$')
        sd_pattern = re.compile(r'^/dev/sd[a-z]$')  # Matches /dev/sda, /dev/sdb, etc.
        nvme_pattern = re.compile(r'^/dev/nvme[0-9]+$')  # Matches /dev/sda, /dev/sdb, etc.

        # Check for /dev/sata* devices first
        sata_devices = glob.glob('/dev/sata*')
        if sata_devices:
            self.devices.extend([d for d in sata_devices if sata_pattern.match(d)])

        # If no SATA devices or to complement them, check for /dev/sd* devices
        if not self.devices:
            sd_devices = glob.glob('/dev/sd*')
            if sd_devices:
                self.devices.extend([d for d in sd_devices if sd_pattern.match(d)])

        # If still no devices or to complement, check for /dev/sg* devices
        if not self.devices:
            sg_devices = glob.glob('/dev/sg*')
            self.devices.extend(sg_devices)  # Assuming /dev/sg* devices don't need filtering for this example

        # Always add any /dev/nvme* devices, excluding partitions and nvme-fabrics
        nvme_devices = glob.glob('/dev/nvme*')
        if nvme_devices:
            self.devices.extend([d for d in nvme_devices if 'fabrics' not in d and nvme_pattern.match(d)])

        return self.devices

    def read_smartdata_for_all_devices(self):
        if not self.check_smartctl_available():
            return {"error": "smartctl command is not available. Please install smartmontools."}

        self.list_devices()
        logging.info(f"Getting S.M.A.R.T. data for devices: {self.devices}...")

        self.smart_data = {}
        for device in self.devices:
            if device.startswith("/dev/nvme"):
                smart_data = self.get_nvme_status(device)
            else:
                smart_data = self.get_smart_data(device)

            self.smart_data[device] = smart_data

        return self.smart_data

    def print_all_details(self):
        """Print details of each Docker Compose project."""
        if not self.smart_data:
            logging.info("No smart data available.")
            return

        logging.info(json.dumps(self.smart_data, indent=4))
