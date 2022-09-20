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
# Create a python docker container to run gunicorn and celery
FROM continuumio/miniconda3:4.12.0 as manyfews
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

# https://pythonspeed.com/articles/conda-docker-image-size/
# Create the environment:
COPY ../config/manyFEMSenv.yml .
RUN conda env create -f manyFEMSenv.yml

# Make RUN commands use the new environment:
RUN echo "conda activate ManyFEWS" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# Demonstrate the environment is activated:
RUN echo "Make sure django is installed:"
RUN python -c "import django"

# The code to run when container is started:
COPY ../entrypoint.sh .
COPY --from=build_node /app .
COPY ../Data /Data

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]

# Export static files from Django for nginx
ENV zentra_un=foo zentra_pw=bar STATIC_ROOT='/app/static'
RUN mkdir static && \
    python manage.py collectstatic --noinput

EXPOSE 5000
CMD ["python", "manage.py", "runserver", "0.0.0.0:5000"]


# ----------------------------------------------------------------------------
# Deployment stage
FROM nginx:stable-alpine as deploy
COPY --from=manyfews /app/static /var/www/html/static
