# Import the class from the file where it's defined (if in a different file, e.g., docker_manager.py)
from docker_compose_manager import DockerComposeManager

# Create an instance of the DockerComposeManager
manager = DockerComposeManager()

# Fetch all Docker Compose projects
projects = manager.list_compose_projects()

# Print the project details
manager.print_projects_details(projects)