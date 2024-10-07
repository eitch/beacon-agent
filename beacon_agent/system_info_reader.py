import subprocess
import platform
import socket
import logging


class SystemInfoReader:
    def __init__(self):
        self.info = {
            'os': 'Unknown',
            'version': 'Unknown',
            'kernel': self.get_kernel_version(),
            'hostname': platform.node(),
            'ipv4_addresses': [],
            'ipv6_addresses': []
        }
        self.get_os_info()
        self.get_ip_addresses()
        logging.info("Enabled SystemInfoReader")

    @staticmethod
    def get_kernel_version():
        """Fetch the kernel version using uname"""
        return platform.release()

    def get_os_info(self):
        """Try to fetch OS info from lsb_release or /etc/VERSION"""
        if self.try_lsb_release():
            return
        self.try_etc_version()

    def try_lsb_release(self):
        """Try to fetch OS info using lsb_release command"""
        try:
            output = subprocess.check_output(['lsb_release', '-a'], stderr=subprocess.STDOUT).decode()
            for line in output.splitlines():
                if "Distributor ID" in line:
                    self.info['os'] = line.split(':')[1].strip()
                elif "Release" in line:
                    self.info['version'] = line.split(':')[1].strip()
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def try_etc_version(self):
        """Try to fetch OS info from /etc/VERSION file"""
        try:
            with open('/etc/VERSION', 'r') as version_file:
                for line in version_file:
                    if 'productversion' in line.lower():
                        self.info['os'] = 'Synology DSM'
                        self.info['version'] = line.split('=')[1].strip()
        except FileNotFoundError:
            pass

    def get_ip_addresses(self):
        """Get all IPv4 and IPv6 addresses, skipping Docker, localhost, and link-local IPv6 addresses"""
        try:
            # First, attempt using psutil
            import psutil
            addresses = psutil.net_if_addrs()
            for iface_name, iface_addrs in addresses.items():
                if 'docker' not in iface_name.lower() and 'br-' not in iface_name.lower():
                    for addr in iface_addrs:
                        if addr.family == socket.AF_INET and addr.address != '127.0.0.1':  # IPv4
                            self.info['ipv4_addresses'].append(addr.address)
                        elif addr.family == socket.AF_INET6 and not addr.address.startswith(
                                'fe80') and addr.address != '::1':  # IPv6
                            self.info['ipv6_addresses'].append(addr.address)
        except ImportError:
            # Fallback: use subprocess to get IPs via system commands (ip or ifconfig)
            self.get_ip_addresses_fallback()

    def get_ip_addresses_fallback(self):
        """Fallback method to get IP addresses using system commands if psutil is not available"""
        try:
            # Attempt to use 'ip' command
            output = subprocess.check_output(['ip', 'addr'], stderr=subprocess.STDOUT).decode()
            self.parse_ip_command_output(output)
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                # Fallback to 'ifconfig' command if 'ip' is not available
                output = subprocess.check_output(['ifconfig'], stderr=subprocess.STDOUT).decode()
                self.parse_ifconfig_output(output)
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass  # No fallback available

    def parse_ip_command_output(self, output):
        """Parse the output of the 'ip addr' command to extract IPs"""
        lines = output.splitlines()
        current_interface = None
        for line in lines:
            line = line.strip()
            if line.startswith('inet '):
                ip = line.split()[1].split('/')[0]
                if ip != '127.0.0.1' and current_interface and 'docker' not in current_interface and 'br-' not in current_interface:
                    self.info['ipv4_addresses'].append(ip)
            elif line.startswith('inet6 '):
                ip = line.split()[1].split('/')[0]
                if ip != '::1' and not ip.startswith(
                        'fe80') and current_interface and 'docker' not in current_interface and 'br-' not in current_interface:
                    self.info['ipv6_addresses'].append(ip)
            elif line and not line.startswith(('link/', 'valid_lft')):
                current_interface = line.split(':')[1].strip() if ':' in line else None

    def parse_ifconfig_output(self, output):
        """Parse the output of the 'ifconfig' command to extract IPs"""
        lines = output.splitlines()
        current_interface = None
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('inet', 'inet6', 'ether')):
                current_interface = line.split()[0]
            elif line.startswith('inet '):
                ip = line.split()[1]
                if ip != '127.0.0.1' and current_interface and 'docker' not in current_interface and 'br-' not in current_interface:
                    self.info['ipv4_addresses'].append(ip)
            elif line.startswith('inet6 '):
                ip = line.split()[1]
                if ip != '::1' and not ip.startswith(
                        'fe80') and current_interface and 'docker' not in current_interface and 'br-' not in current_interface:
                    self.info['ipv6_addresses'].append(ip)

    def get_system_info(self):
        """Return the gathered system information"""
        return self.info


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    system_info = SystemInfoReader()
    logging.info(system_info.get_system_info())
