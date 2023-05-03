# Production Deployment

Production deployment of the ManyFEWS tool is acheived using Docker. Each part of the application is containerized within the [Dockerfile](../Dockerfile), which implements a [multi-stage build process](https://docs.docker.com/build/building/multi-stage/). The finer details of this are documented within the Dockerfile itself.

## Azure

An [azure-pipelines.yml](../.github/azure/azure-pipelines.yml) file controls deployment to Azure. The nginx container is hosted using within the Durham University Advanced Web Hosting project Azure App Service plan. This provides a reverse-proxy to the WSGI gateway located within the internal network.

![img](https://user-images.githubusercontent.com/1038320/198277827-21862c80-695c-431a-9b74-ba3337b23cec.png)

All secret keys are stored as Azure Pipelines variables and are applied to the Docker containers as environment variables at runtime. 

Developers should take care to ensure that no application secrets are stored as code in this repository.

### CI/CD Workflow

Pushing to the `release` branch in GitHub will trigger the CI/CD workflow. This will run tests locally and trigger the azure pipeline to build and release the Docker containers. Follow the process documented in [README.md](../README.md#release-branch) to push to `release`.

The [`azure-pipelines.yml`](../.github/azure/azure-pipelines.yml) file handles automated deployment. The first stage (Build) builds the Docker images and pushes them to the [DurhamARC DockerHub](https://hub.docker.com/orgs/durhamarc/repositories) organisation. The Release stage releases the code to the production servers.

Two `docker compose` files are included under the [azure](../.github/azure) directory. [`docker-compose.azure.yml`](../.github/azure/docker-compose.azure.yml) configures the [manyfews-web](https://hub.docker.com/repository/docker/durhamarc/manyfews-web) image within the Azure App Service plan. The [`docker-compose.backend.yml`](../.github/azure/docker-compose.backend.yml) is used to deploy the backend containers (see the above image), including the external containers (RabbitMQ, PostGIS).

## Manual

A number of `docker-compose` configurations are included within this project, both for [local](../docker-compose.yml) and [production](../docker-compose.production.yml) deployment. Additional settings can be customised by creating a `docker-compose.override.yml` file per the [compose documentation](https://docs.docker.com/compose/extends/).

You should create a `.env` file using [`.env.CI`](../manyfews/manyfews/.env.CI) as a base. Place this within the root of the project directory and customise the variables as required with your API keys. It will be picked up by `docker compose` to populate environment variables.

The production example uses [Træfik](https://traefik.io/traefik) to reverse proxy the application stack and request certificates. It also includes [watchtower](https://github.com/containrrr/watchtower) to monitor for and pull base image updates. 

### Manual production deployment steps:

  *  Install [Docker](https://www.docker.com/)  
     * Docker-compose has been included in the base docker package since version 4.4.2.  
     * Older versions of Docker may require installation of the [plugin](https://docs.docker.com/compose/install/linux/) or the [standalone](https://docs.docker.com/compose/install/other/) `docker-compose` command.
  *  Clone the git repo (or at a minimum, `docker-compose.yml` and `docker-compose.production.yml`)
  *  Move `docker-compose.production.yml` to `docker-compose.override.yml`
  *  Copy `manyfews/manyfews/.env.CI` to `.env`
  *  Edit `.env` to populate it with the production environment variables.
  *  Run `docker compose pull && docker compose up -d`
     * Note that if you decided to install the standalone command, this is `docker-compose`, with a hyphen.
  *  Check that the ports for `:80` and `:443` are open to serve http+s traffic.
  *  Wait for certificate issuance while Traefik uses Let'sEncrypt to request a TLS cert.


### Environment Variables
The following environment variables *must* be set in the `.env` file to use this configuration:

```shell
ALLOWED_HOSTS=example.com
CSRF_TRUSTED_ORIGINS=https://example.com,http://example.com
DOMAIN=example.com
```

The `DOMAIN` variable is used by the compose file to tell Træfik the domain to request certificates using [Let's Encrypt](https://letsencrypt.org/docs/). You should ensure that your domain is set up with an `A` and/or `CNAME` DNS record (as appropriate) pointing to your production server's IP address.

The `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` variables tell Django's security features to allow HTTP requests originating from your custom domain. 

The [settings.py](../manyfews/manyfews/settings.py) file serves as the master list of configurable environment variables. A sample `.env` file for Docker deployment is also shared within this repository ([.env.CI](../manyfews/manyfews/.env.CI)).
