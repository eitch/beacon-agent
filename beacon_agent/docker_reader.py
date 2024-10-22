import shutil
import subprocess
import json
import logging


class DockerReader:
    def __init__(self, config):
        """Initialize the DockerReader."""
        self.enabled = config.get_config_value(["docker", "enabled"], default=False)
        if not self.enabled:
            return

        if shutil.which("docker") is None:
            logging.error("docker command is not available. Docker reading disabled!")
            self.enabled = False
            return

        logging.info("Enabled DockerReader")

    @staticmethod
    def _run_command(command):
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

    def _get_docker_containers(self):
        """Get details of all running Docker containers."""
        if shutil.which("docker") is None:
            logging.error("docker command is not available. Please disable docker reader!")
            return []

        command = ["docker", "ps", "--all", "--format", "{{json .}}"]
        output = self._run_command(command)

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
                logging.warning(f"Skipping malformed line: {line}")
        return containers

    def list_projects(self):
        """List Docker containers, grouping by label com.docker.compose.project"""
        if not self.enabled:
            return None

        containers = self._get_docker_containers()
        projects = {}

        for container in containers:
            # Docker Compose projects usually have the project name as a label or part of the container name
            labels = self._parse_docker_labels(container.get('Labels', {}))
            compose_project = labels.get('com.docker.compose.project')
            if not compose_project:
                compose_project = container['Names'].split("_")[0]  # Guessing from container name

            # Collect container details
            container_details = {
                'container_id': container['ID'],
                'image': container['Image'],
                'state': container['State'],
                'status': container['Status'],
                'name': container['Names'],
                'labels': labels
            }

            if compose_project not in projects:
                projects[compose_project] = []

            projects[compose_project].append(container_details)

        return projects

    @staticmethod
    def _parse_docker_labels(label_str):
        """
        Parse the Docker labels string into a dictionary.

        Args:
            label_str (str): The Docker labels string (comma-separated key-value pairs).

        Returns:
            dict: Parsed labels as a dictionary.
        """

        # before we can do such splitting, we need to fix broken labels:
        label_str = label_str.replace(", ", " ")

        # Split the string by commas to get individual key-value pairs
        if not label_str:
            logging.warning(f"No Docker labels string provided: {label_str}")
            return {}
        label_pairs = label_str.split(',')

        # Create a dictionary from the key-value pairs
        labels_dict = {}
        for pair in label_pairs:
            if "=" not in pair:
                logging.warning(f"Invalid Docker label: {pair}")
                continue
            key, value = pair.split('=', 1)  # Split each pair at the first '=' sign
            labels_dict[key] = value

        return labels_dict

    @staticmethod
    def print_projects_details(projects):
        """Print details of each Docker project."""
        if not projects:
            logging.info("No Docker projects found.")
            return

        for project, containers in projects.items():
            logging.info(f"Project: {project}")
            for container in containers:
                logging.info(f"  Container: {container['name']}:\n{json.dumps(container, indent=2)}")
                logging.info("")


if __name__ == "__main__":
    from .custom_logging import CustomLogging
    from .agent_config import AgentConfig
    custom_logging = CustomLogging()
    custom_logging.configure_logging()

    with open('example_config.json', 'r') as file:
        config = json.load(file)
    config = AgentConfig(config)

    docker = DockerReader(config)
    projects = docker.list_projects()
    docker.print_projects_details(projects)
