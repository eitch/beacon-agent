import docker
import logging

class DockerComposeManager:
    def __init__(self):
        """Initialize the Docker client."""
        self.log = logging.getLogger(__name__)
        self.log.info("Started Beacon-Agent")
        self.client = docker.from_env()

    def list_compose_projects(self):
        """
        List all Docker Compose projects and their container details.

        Returns:
            projects (dict): A dictionary of Docker Compose projects,
                             where the key is the project name and
                             the value is a list of container details.
        """
        containers = self.client.containers.list()  # List all running containers
        projects = {}

        for container in containers:
            labels = container.labels
            # Docker Compose projects are identified by this label
            compose_project = labels.get('com.docker.compose.project')

            if compose_project:
                container_details = {
                    'container_id': container.id,
                    'image': container.image.tags[0] if container.image.tags else container.image.short_id,
                    'status': container.status,
                    'name': container.name,
                }

                if compose_project not in projects:
                    projects[compose_project] = []

                projects[compose_project].append(container_details)

        return projects

    def get_project_containers(self, project_name):
        """
        Get the details of all containers within a specific Docker Compose project.

        Args:
            project_name (str): The name of the Docker Compose project.

        Returns:
            containers (list): A list of container details within the project.
        """
        projects = self.list_compose_projects()
        return projects.get(project_name, [])

    def print_project_details(self, project_name=None):
        """
        Print the details of a specific Docker Compose project, or all projects if none is specified.

        Args:
            project_name (str, optional): The name of the Docker Compose project.
                                          If None, details of all projects will be printed.
        """
        if project_name:
            containers = self.get_project_containers(project_name)
            if containers:
                self.log.info(f"Project: {project_name}")
                for container in containers:
                    self.log.info(f"  Container Name: {container['name']}")
                    self.log.info(f"    Image: {container['image']}")
                    self.log.info(f"    Status: {container['status']}")
                    self.log.info(f"    Container ID: {container['container_id']}")
                self.log.info()
            else:
                self.log.info(f"No containers found for project: {project_name}")
        else:
            projects = self.list_compose_projects()
            if not projects:
                self.log.info("No Docker Compose projects found.")
                return

            for project, containers in projects.items():
                self.log.info(f"Project: {project}")
                for container in containers:
                    self.log.info(f"  Container Name: {container['name']}")
                    self.log.info(f"    Image: {container['image']}")
                    self.log.info(f"    Status: {container['status']}")
                    self.log.info(f"    Container ID: {container['container_id']}")
                self.log.info()
