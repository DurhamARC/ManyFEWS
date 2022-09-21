# ----------------------------------------------------------------------------
# Build node / Frontend assets
FROM node:alpine3.15 as build_node
MAINTAINER Samantha Finnigan <samantha.finnigan@durham.ac.uk>, ARC Durham University

# Based on https://cli.vuejs.org/guide/deployment.html#docker-nginx
WORKDIR /app

# Install Python (required for node-gyp)
RUN apk add --update python3 make g++ && \
    rm -rf /var/cache/apk/*

# Install app dependencies
COPY manyfews/package.json .
RUN npm install

# Copy files and build app
COPY manyfews/ .
RUN npm run build


# ----------------------------------------------------------------------------
# Create conda environment
FROM continuumio/miniconda3:4.12.0 as build_python

# https://pythonspeed.com/articles/conda-docker-image-size/
# Create the environment:
COPY ../config/manyFEWSdocker.yml .
RUN conda env create -f manyFEWSdocker.yml

# Install conda-pack:
RUN conda install -c conda-forge conda-pack

# Use conda-pack to create a standalone enviornment
# in /venv:
RUN conda-pack -n ManyFEWS -o /tmp/env.tar && \
  mkdir /venv && cd /venv && tar xf /tmp/env.tar && \
  rm /tmp/env.tar

# We've put venv in same path it'll be in final image,
# so now fix up paths:
RUN /venv/bin/conda-unpack

# Export static files from Django for nginx
WORKDIR /app
SHELL ["/bin/bash", "--login", "-c"]
ENV zentra_un=foo zentra_pw=bar STATIC_ROOT='/app/static'
COPY --from=build_node /app .
RUN source /venv/bin/activate && \
    mkdir -p /app/static && \
    python manage.py collectstatic --noinput


# ----------------------------------------------------------------------------
# Create a python docker container to run gunicorn and celery
FROM debian:bullseye-slim as manyfews
MAINTAINER Samantha Finnigan <samantha.finnigan@durham.ac.uk>, ARC Durham University
WORKDIR /app

# set environment variables (don't buffer stdout, don't write bytecode)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Add a celery user to avoid running as root
RUN mkdir -p /var/log/celery/ /var/run/celery/ &&\
    useradd -G root celery && \
    chgrp -Rf root /var/log/celery/ /var/run/celery/ && \
    chmod -Rf g+w /var/log/celery/ /var/run/celery/ && \
    chmod g+w /etc/passwd

# Copy /venv from the previous stage:
COPY --from=build_python /venv /venv
ENV PATH /opt/conda/bin:$PATH

# Make RUN commands use the new environment:
RUN echo "source /venv/bin/activate" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# Demonstrate the environment is activated:
RUN echo "Make sure django is installed:" && \
    python -c "import django"

# The code to run when container is started:
COPY manyfews/ .
COPY Data /Data

EXPOSE 5000
CMD ["python", "manage.py", "runserver", "0.0.0.0:5000"]


# ----------------------------------------------------------------------------
# Deployment stage
FROM nginx:stable-alpine as deploy
COPY --from=build_python /app/static /var/www/html/static
