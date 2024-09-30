import  logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s.%(msecs)03d %(module)s %(levelname)s:\t%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

from docker_compose_reader import DockerComposeReader
docker = DockerComposeReader()
projects = docker.list_compose_projects()
docker.print_projects_details(projects)