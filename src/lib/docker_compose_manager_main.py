# Import the DockerComposeManager class from docker_compose_manager.py
from docker_compose_manager import DockerComposeManager

# Create an instance of the DockerComposeManager
manager = DockerComposeManager()

# Call the method to print all Docker Compose project details
manager.print_project_details()

# Or, to get the details of a specific project (replace 'your_project_name' with the actual name)
# manager.print_project_details("your_project_name")