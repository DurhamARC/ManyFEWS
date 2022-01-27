# Development

ManyFEWS is built using [Django](https://www.djangoproject.com), using [GeoDjango](https://docs.djangoproject.com/en/3.2/ref/contrib/gis/) to work with geographical data in a [PostGIS](https://postgis.net) database. It uses [celery](https://docs.celeryproject.org/en/stable/index.html) to run scheduled and asyncronous tasks.

## Prerequisites

Make sure you have the following installed:

 * conda (e.g. [miniconda](https://docs.conda.io/en/latest/miniconda.html) if you don't already have conda installed)
 * [RabbitMQ](https://www.rabbitmq.com/download.html)
 * [PostgreSQL](https://www.postgresql.org/download/) and [PostGIS](https://postgis.net/docs/manual-3.2/postgis_installation.html) - see (see https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/postgis/)

## Setup

1. Clone this repository, open a terminal and cd to the repository root.
2. Install conda (I recommend [miniconda](https://docs.conda.io/en/latest/miniconda.html) if you don't have conda installed).
3. Install and activate the ManyFEWS conda environment:

   ```bash
   $ conda env create --file condaEnv/manyFEMSenv.yml
   $ conda activate ManyFEWS
   ```

4. Set up the pre-commit hook (see `.pre-commit-config.yaml`) to run `black` before committing:

   ```bash
   pre-commit install
   ```

5. Create a `manyfews` user and database and enable the PostGIS extension:

   ```bash
   $ createuser manyfews --createdb --pwprompt
   Enter password for new role: manyfews
   Enter it again: manyfews
   $ createdb manyfews -O manyfews
   $ psql manyfews
   > CREATE EXTENSION postgis;
   ```

7. Run the django database migrations to set up the database:

   ```bash
   python manage.py migrate
   ```

8. Create an admin user:

   ```bash
   python manage.py createsuperuser
   ```

   (Follow the prompts to add a username, email and password.)

9. Run the django app in development mode:

  ```bash
  cd manyfews
  python manage.py runserver
  ```

  Go to http://127.0.0.1:8000/ and check that the app works.

10. In another terminal, run a celery worker and celery beat, to enable scheduled and asynchronous tasks to be run (using [django-celery-beat](https://django-celery-beat.readthedocs.io/en/latest/#)):

    ```bash
    celery -A manyfews worker -B -l DEBUG --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ```

11. Go to the http://127.0.0.1:8000/admin and log in with the user you set up earlier. Go to **Periodic tasks** and set up a periodic task to run a scheduled task (e.g. `calculations.hello_celery`). You should be able to see the output in the terminal running `celery`.


## Loading sample data

This is a temporary step until we can populate the database with data from the model.

Run from the top `manyfews` directory:

```bash
python manage.py shell
>>> exec(open('webapp/load.py').read())
```
