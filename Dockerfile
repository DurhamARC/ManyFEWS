#
# Dockerfile: Build containers for the ManyFEWS application
#
# This is a multistage Dockerfile which produces a set of containers
# for the application. The stages are as follows:
#
#  1. (build_node)   – Build Node.js assets for the front-end website
#  2. (build_python) - Install python dependencies with conda and compress them
#  3. (build_static) - Export all static resources from Django
#
# These three containers are discarded at runtime and only produce compressed
# assets which are picked up by the following stages:
#
#  4. (manyfews)     - Create base image for the python containers
#  5. (celery)       - Configure the manyfews base image for running Celery,
#                        which provides a task queue to run jobs
#  6. (gunicorn)     - Configure the manyfews base image for running Gunicorn,
#                        used as a WSGI gateway for the Django app
#  7. (web)          - Nginx container to serve static files for the application
#                        and forward API requests to the WSGI server.
#
# Using a multistage Dockerfile increases the complexity of the build process,
#  but results in a significantly smaller final image. This is important when
#  we push the app up to a container repo, as excluding all the Conda and Node
#  dependencies saves about ~1.7GB of space (final image ~300MB instead of 2G).
#
# See: https://docs.docker.com/build/building/multi-stage/ for more info.
#
# ----------------------------------------------------------------------------
# Build node / Frontend assets
FROM node:alpine3.15 as build_node
MAINTAINER Samantha Finnigan <samantha.finnigan@durham.ac.uk>, ARC Durham University

# Install Python (required for node-gyp)
RUN apk add --update python3 make g++ && \
    rm -rf /var/cache/apk/*

# Based on https://cli.vuejs.org/guide/deployment.html#docker-nginx
WORKDIR /app

# Install app dependencies
COPY manyfews/package.json .
RUN npm install

# Copy files and build app
COPY manyfews/webpack.config.js .
COPY manyfews/webapp/assets webapp/assets
RUN npm run build


# ----------------------------------------------------------------------------
# Create conda environment
FROM continuumio/miniconda3:4.12.0 as build_python

# https://pythonspeed.com/articles/conda-docker-image-size/
# Create the environment:
COPY config/manyFEWSdocker.yml .
RUN --mount=type=cache,target=/opt/conda/pkgs \
    conda env create -f manyFEWSdocker.yml

# Install conda-pack:
RUN --mount=type=cache,target=/opt/conda/pkgs \
    conda install -c conda-forge conda-pack

# Use conda-pack to create a standalone enviornment
# in /venv:
RUN conda-pack -n ManyFEWS -o /tmp/env.tar && \
  mkdir /venv && cd /venv && tar xf /tmp/env.tar && \
  rm /tmp/env.tar

# We've put venv in same path it'll be in final image,
# so now fix up paths:
RUN /venv/bin/conda-unpack

WORKDIR /app
SHELL ["/bin/bash", "--login", "-c"]


# ----------------------------------------------------------------------------
# Create static files for ManyFEWS site using django (for deployment on standard webserver)
FROM build_python as build_static
# Set dummy variables for Zentra so that app doesn't error out
# and the STATIC_ROOT var for the location to write static files
ENV ZENTRA_UN=foo ZENTRA_PW=bar STATIC_ROOT='/app/static'
COPY manyfews/ .
COPY --from=build_node /app/webapp/static/index-bundle.js /app/webapp/static/

# Export static files from Django for nginx
RUN source /venv/bin/activate && \
    mkdir -p /app/static && \
    python manage.py collectstatic --noinput


# ----------------------------------------------------------------------------
# Create a python docker container base for gunicorn and celery
FROM debian:bullseye-slim as manyfews
MAINTAINER Samantha Finnigan <samantha.finnigan@durham.ac.uk>, ARC Durham University
WORKDIR /app

# set environment variables (don't buffer stdout, don't write bytecode)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV BASH_ENV "~/.bashrc"
# Avoid <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1129)>
ENV SSL_CERT_FILE /etc/ssl/certs/ca-certificates.crt

# Replicate environment from miniconda image
RUN apt-get update -q && \
    apt-get install -q -y --no-install-recommends \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy /venv from the previous stage:
COPY --from=build_python /venv /venv
COPY --from=build_python /opt/conda/envs/ManyFEWS/share/eccodes/definitions /opt/conda/envs/ManyFEWS/share/eccodes/definitions
ENV PATH /opt/conda/bin:$PATH

# Make RUN commands use the new environment:
RUN echo "source /venv/bin/activate" >> ${HOME}/.bashrc
SHELL ["/bin/bash", "--login", "-c"]
ENTRYPOINT ["/bin/bash", "--login", "-c"]

# Demonstrate the environment is activated:
RUN echo "Make sure django is installed:" && \
    python -c "import django"

# The code to run when container is started:
COPY manyfews/ .
COPY Data /Data

CMD ["python manage.py migrate && \
      python manage.py runserver 0.0.0.0:5000"]


# ----------------------------------------------------------------------------
# Create celery container
FROM manyfews as celery

# Add a celery user to avoid running as root
RUN mkdir -p /var/log/celery/ /var/run/celery/ &&\
    useradd -G root -u 1000 celery && \
    chgrp -Rf root /var/log/celery/ /var/run/celery/ && \
    chmod -Rf g+w /var/log/celery/ /var/run/celery/ && \
    chmod g+w /etc/passwd && \
    mkdir -p /home/celery && \
    chmod 775 /home/celery

USER celery
RUN echo "source /venv/bin/activate" >> /home/celery/.bashrc

CMD ["celery -A manyfews worker --loglevel=INFO \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler -E"]


# ----------------------------------------------------------------------------
# Create gunicorn container
FROM manyfews as gunicorn

EXPOSE 5000
CMD ["python manage.py migrate && \
      python manage.py loaddata webapp/fixtures/initial_data.json && \
      gunicorn --timeout=300 --log-file=- --bind=0.0.0.0:5000 manyfews.wsgi"]


# ----------------------------------------------------------------------------
# Deployment stage
FROM nginx:stable-alpine as web
COPY --from=build_static /app/static /var/www/html/static
COPY config/subsite.conf /etc/nginx/conf.d/default.conf
COPY config/nginx-configure-upstream.sh /docker-entrypoint.d/40-configure-upstream.sh
COPY config/50x.html /usr/share/nginx/html/50x.html
RUN chmod +x /docker-entrypoint.d/40-configure-upstream.sh

ENV UPSTREAM_SERVER=localhost
ENV UPSTREAM_PORT=5000

