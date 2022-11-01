# ManyFEWS

[![Actions Status](https://github.com/DurhamARC/ManyFEWS/workflows/Unit%20Tests/badge.svg)](https://github.com/DurhamARC/ManyFEWS/actions)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov.io](https://codecov.io/gh/DurhamARC/ManyFEWS/branch/main/graphs/badge.svg)](https://codecov.io/gh/DurhamARC/ManyFEWS/branch/main)

ManyFEWS (the Many Flood Early Warning System) can be deployed by a community where there is currently no such system in place. The system uses weather forecast information from the [Global Ensemble Forecast System](https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast) produced by [NOAA](https://www.noaa.gov), coupled with a catchment hydrological model and a flood inundation model. The user interface is in development and will allow for the issuing of the alerts via a messaging service. A key innovation in the system is the use of statistical emulation of the 2D hydraulic flood model to enable rapid warnings to be generated within an uncertainty framework.

The initial version of the system (v1.0) will become available from Autumn 2022. Funding for the future development of the system is currently being secured.

### Durham University Project Team

| Project Member                                   | Contact address                                                      | Role                             | Unit                                                                                |
|--------------------------------------------------|----------------------------------------------------------------------|----------------------------------|-------------------------------------------------------------------------------------|
| Dr. [Samantha Finnigan](https://github.com/sjmf) | [samantha.finnigan@dur.ac.uk](mailto:samantha.finnigan@durham.ac.uk) | Research Software Engineer (RSE) | [Advanced Research Computing](https://www.dur.ac.uk/arc/rse/)                       |
| Dr. [Jiada Tu](https://github.com/Abel-Durham)   | [jiada.tu@dur.ac.uk](mailto:jiada.tu@durham.ac.uk)                   | Research Software Engineer (RSE) | [Advanced Research Computing](https://www.dur.ac.uk/arc/rse/)                       |
| Dr. [Sim Reaney](https://github.com/simreaney)   | [sim.reaney@dur.ac.uk](mailto:sim.reaney@durham.ac.uk)               | Java Flood One Co-Investigator   | [Department of Geography](https://www.durham.ac.uk/departments/academic/geography/) |

The initial implementation of the ManyFEWS tool was architected and developed in Python/Django by [Alison Clarke](https://github.com/alisonrclarke).

### Acknowledgements

The development of the new flood early warning system was funded under the [Java Flood One](https://www.durham.ac.uk/research/institutes-and-centres/hazard-risk-resilience/research/current-projects/indonesia-java-flood-one/) project (UKRI grant ref. [NE/S00310X/1 ](https://gtr.ukri.org/projects?ref=NE%2FS00310X%2F1)) funded by [UKRI’s NERC](https://nerc.ukri.org) and Indonesia’s [Ristekdikti](http://litbangda.ristekdikti.go.id).

The project is run by [Durham University](https://www.dur.ac.uk), the [UK Centre for Ecology and Hydrology](https://www.ceh.ac.uk), [Bandung Insitute of Technology](https://www.itb.ac.id) and local NGO in Indonesia [Jaga Balai](https://instagram.com/jagabalai?utm_medium=copy_link).

## Getting Started

See [DEVELOPMENT.md](DEVELOPMENT.md) for details of how to set up a development instance, and [SCHEDULING.md](SCHEDULING.md) for how to set up the scheduled tasks to run the weather modelling and create alerts.

### Docker

A multi-stage [Dockerfile](Dockerfile) is included in this repository. Pre-built Docker images are available for:

* The [WSGI server](https://hub.docker.com/r/durhamarc/manyfews-gunicorn)
* The [Web frontend](https://hub.docker.com/r/durhamarc/manyfews-web)
* The [Celery backend](https://hub.docker.com/r/durhamarc/manyfews-gunicorn)

### Running Locally

The [docker-compose.yml](docker-compose.yml) file in the root of this repository includes the project dependencies and can be run to set up an instant working development system. For manual setup instructions, see [DEVELOPMENT.md](DEVELOPMENT.md).

### Deployment

A couple of different production deployment possibilities are documented in [PRODUCTION.md](PRODUCTION.md). We include a production [docker-compose](docker-compose.production.yml) file for running the system behind a [Træfik](https://traefik.io/traefik) load balancer.

## Contributing

Please feel free to comment on and create [issues](issues). When creating an issue, please use the correct issue template, e.g. for Bug Reports or Feature Requests.

### `main` Branch
Protected and should only be pushed to via pull requests. Should be considered stable and a representation of production code.

### `devel` Branch
Should be considered fragile, code should compile and run but features may be prone to errors.

### `feature` Branches
Feature branches should be created from the `main` and `devel` branches to track commits per feature being worked on. External developers should fork the repository and add their commits to a Pull Request. This follows the ["github-flow" model of branching](https://docs.github.com/en/get-started/quickstart/github-flow).

### `release` Branch
Pushing to the `release` branch triggers the CI/CD workflow to build the Docker images and upload them to the [DurhamARC DockerHub](https://hub.docker.com/orgs/durhamarc/) repositories, then release to Azure and the backend servers. The release branch is protected and can only be pushed to by authorized members (currently [@sjmf](https://github.com/sjmf) and [@Abel-Durham](https://github.com/Abel-Durham)).

The release branch is managed by rebasing on top of the `main` branch and creating a tag. For example:

```shell
$ git checkout release
$ git rebase main
$ git tag -a v1.x -m "Release v1.x"
$ git push origin release v1.x
$ git checkout main
```


## Built With

We are using the following frameworks and tools to develop this software:

* [Django](https://www.djangoproject.com/)
* [Celery](https://docs.celeryq.dev/en/stable/index.html)
* [Docker](https://docker.io/)

A CI/CD pipeline is used to test and release this software, using [GitHub Actions](https://github.com/features/actions) and [Azure Pipelines](https://azure.microsoft.com/en-gb/products/devops/pipelines/). 


## License
This work is licensed under the [GNU General Public License v3.0](LICENSE), which allows Commercial use, Modification, and Distribution, but does not admit any liability or warranty for use of this code.

[//]: # (## Citation)
[//]: # ()
[//]: # (Please cite the associated papers for this work if you use this code:)
[//]: # ()
[//]: # (```)
[//]: # (@article{xxx2021paper,)
[//]: # (  title={Title},)
[//]: # (  author={Author},)
[//]: # (  journal={arXiv},)
[//]: # (  year={2021})
[//]: # (})
[//]: # (```)

[//]: # (## Usage)
[//]: # ()
[//]: # (Any links to production environment, video demos and screenshots.)
[//]: # ()
[//]: # (## Roadmap)
[//]: # ()
[//]: # (- [x] Initial Research  )
[//]: # (- [x] Minimum viable product: )
[//]: # (- [ ] Alpha Release  )
[//]: # (- [ ] Feature-Complete Release  )
