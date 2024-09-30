import subprocess
import json
import logging

class DockerComposeReader:
    def __init__(self):
        """Initialize the DockerComposeReader."""

    def run_command(self, command):
        """
        Run a shell command and return the output.
        Handles permission errors and other issues gracefully.
        """
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode != 0:
                # Check for permission denied error in stderr
                if "permission denied" in result.stderr.lower():
                    logging.error(f"Permission denied while running command: {' '.join(command)}")
                else:
                    logging.error(f"Error running command {command}: {result.stderr}")
                return None

            return result.stdout

        except PermissionError as e:
            logging.error(f"PermissionError: {e}. You may need elevated privileges to run this command.")
            return None

        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to execute command: {e}")
            return None

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return None

    def get_docker_containers(self):
        """Get details of all running Docker containers."""
        command = ["docker", "ps", "--format", "{{json .}}"]
        output = self.run_command(command)

        if not output:
            return []

        containers = []
        # Each line is a JSON object representing a container, so parse each one
        for line in output.strip().split('\n'):
            try:
                json_object = json.loads(line)
                # print(json_object)
                containers.append(json_object)  # Parse each line as JSON
            except json.JSONDecodeError:
                self.log.warning(f"Skipping malformed line: {line}")
        return containers

    def list_compose_projects(self):
        """List Docker Compose projects and their details."""
        containers = self.get_docker_containers()
        projects = {}

        for container in containers:
            # Docker Compose projects usually have the project name as a label or part of the container name
            labels = self.parse_docker_labels(container.get('Labels', {}))
            compose_project = labels.get('com.docker.compose.project')
            if not compose_project:
                compose_project = container['Names'].split("_")[0]  # Guessing from container name

            # Collect container details
            container_details = {
                'container_id': container['ID'],
                'image': container['Image'],
                'status': container['Status'],
                'name': container['Names'],
            }

            if compose_project not in projects:
                projects[compose_project] = []

            projects[compose_project].append(container_details)

        return projects

    def print_projects_details(self, projects):
        """Print details of each Docker Compose project."""
        if not projects:
            logging.info("No Docker Compose projects found.")
            return

        for project, containers in projects.items():
            logging.info(f"Project: {project}")
            for container in containers:
                logging.info(f"  Container Name: {container['name']}")
                logging.info(f"    Image: {container['image']}")
                logging.info(f"    Status: {container['status']}")
                logging.info(f"    Container ID: {container['container_id']}")
            logging.info("")

    @staticmethod
    def parse_docker_labels(label_str):
        """
        Parse the Docker labels string into a dictionary.

        Args:
            label_str (str): The Docker labels string (comma-separated key-value pairs).

        Returns:
            dict: Parsed labels as a dictionary.
        """
        # Split the string by commas to get individual key-value pairs
        label_pairs = label_str.split(',')

        # Create a dictionary from the key-value pairs
        labels_dict = {}
        for pair in label_pairs:
            key, value = pair.split('=', 1)  # Split each pair at the first '=' sign
            labels_dict[key] = value

        return labels_dict
