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
ENV zentra_un=foo zentra_pw=bar STATIC_ROOT='/app/static'
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
      gunicorn --timeout=300 --log-file=- --bind=0.0.0.0:5000 manyfews.wsgi"]


# ----------------------------------------------------------------------------
# Deployment stage
FROM nginx:stable-alpine as web
COPY --from=build_static /app/static /var/www/html/static
COPY config/subsite.conf /etc/nginx/conf.d/default.conf
