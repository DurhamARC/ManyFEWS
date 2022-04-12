# Development

ManyFEWS is built using [Django](https://www.djangoproject.com), using [GeoDjango](https://docs.djangoproject.com/en/3.2/ref/contrib/gis/) to work with geographical data in a [PostGIS](https://postgis.net) database. It uses [celery](https://docs.celeryproject.org/en/stable/index.html) to run scheduled and asyncronous tasks.

## Prerequisites

Make sure you have the following installed:

 * conda (e.g. [miniconda](https://docs.conda.io/en/latest/miniconda.html) if you don't already have conda installed)
 * [RabbitMQ](https://www.rabbitmq.com/download.html)
 * [PostgreSQL](https://www.postgresql.org/download/) and [PostGIS](https://postgis.net/docs/manual-3.2/postgis_installation.html) - see (see https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/postgis/)
 * [Node.js (and npm)](https://nodejs.org/en/)
 * [Chrome](https://www.google.co.uk/chrome/) and a version of [ChromeDriver](https://chromedriver.chromium.org/downloads) which matches the major version of Chrome - ChromeDriver is used for automated browser testing.

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
   > ALTER ROLE manyfews CREATEDB SUPERUSER NOCREATEROLE;
   > CREATE EXTENSION postgis;
   ```

   Exit the postgresql shell using Ctrl-D or typing `\q`.


6. Register a Zentra Cloud account.
   1. Sign up for an account on: `https://zentracloud.com/accounts/login/`;
   2. Then contact the administrator for your Zentra Cloud organisation to add your user account to the organisation.
   Also create a [Bing Maps](https://www.bingmapsportal.com) developer account, and create a basic API key.


7. Set up environment variables in Django.  
   ```bash
   $ cd manyfews
   $ cp .env.CI .env
   $ vi .env
   > replace 'zentraCloudUserName' with your user name of your Zentra cloud account.
   > replace 'zentraCloudPassword' with your password of your Zentra cloud account.
   > replace 'map_api_token' with your Bing Maps API token.
   > replace the lines starting with 'email_' with your SMTP settings (either real settings, or using something like [mailcatcher](https://mailcatcher.me))
   > Save and quit.
   $ cd ..
   ```

8. Run the django database migrations to set up the database:

   ```bash
   cd manyfews
   python manage.py migrate
   ```

9. Create an admin user (still in the `manyfews` directory):

   ```bash
   python manage.py createsuperuser
   ```

   (Follow the prompts to add a username, email and password.)

10. Build the web assets (JavaScript and CSS) using npm:

    ```bash
    npm install
    npm run build
    ```

    `npm install` only needs to be run once, or if a new JavaScript package is added. `npm run build` should be run whenever a JavaScript or Sass file is updated. For development purposes you can run `npm run dev` to build the files on-the-fly whilst editing the JavaScript/Sass, but you should run `npm run build` before committing.

11. Run the tests to check things are installed correctly:

    ```bash
    python manage.py test
    ```

    Note that this will run the browser tests which will open up Chrome and automatically click through the tests.

12. Run the django app in development mode (still in the `manyfews` directory):

    ```bash
    python manage.py runserver
    ```

    Go to http://127.0.0.1:8000/ and check that the app works.

13. In another terminal, run a celery worker and celery beat, to enable scheduled and asynchronous tasks to be run (using [django-celery-beat](https://django-celery-beat.readthedocs.io/en/latest/#)):

    ```bash
    celery -A manyfews worker -B -l DEBUG --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ```

14. Go to the http://127.0.0.1:8000/admin and log in with the user you set up earlier. Go to **Periodic tasks** and set up a periodic task to run a scheduled task (e.g. `calculations.hello_celery`). You should be able to see the output in the terminal running `celery`. See [SCHEDULING.md](SCHEDULING.md) for details of setting up all scheduled tasks to run the model daily. If you would like to see what tasks are queued, run `celery -A manyfews flower` which sets up a web interface at http://localhost:5555/ to let you see the queues.

15. Go to the http://127.0.0.1:8000/admin again. Go to **Zentra devices** (under Calculations) and you should be able to create a new ZentraDevice and select its location.

16. To load some (dummy) flood model parameters, go to http://127.0.0.1:8000/admin and go to **Model versions** (under Calculations). Create a new Model version using the file `Data/MajalayaFloodEmulatorParams-DUMMY-5pcSample.csv` as the parameter file. The parameters will be loaded into the database via a celery task.

17. To load the river channel into the database (to prevent sending alerts about depths in the channel), go to http://127.0.0.1:8000/admin again. Go to **River channels** (under Calculations), create new, and paste in the contents of `Data/channel.geojson` into the box beneath the map.


## Making model changes

Django database models are defined in `models.py` in each app (`calculations`, `webapp`). If you make a change to a model, you need to run the following steps:

```
python manage.py makemigrations
```

This creates a file in the `migrations` directory describing the changes to the model since `makemigrations` was last run.

```
python manage.py migrate
```

This applies all changes from the `migrations` diretories for each app to your database.


## GIS Coordinates

A note on GIS coordinates in different places. The GeoDjango library, based on GEOS, uses (x, y) coordinates for Points,
where x is longitude and y is latitude. LeafletJS used in the front end uses (lat, lon) pairs, i.e. the other way round.
To check values in the database are correct you can use the `ST_AsLatLonText` function, e.g.:

```sql
select ST_AsLatLonText(ST_CENTROID(bounding_box)), ST_X(ST_CENTROID(bounding_box)), ST_Y(ST_CENTROID(bounding_box)) from calculations_aggregateddepthprediction where prediction_date > now();

st_aslatlontext                |        st_x        |        st_y         
-------------------------------+--------------------+---------------------
7°3'53.100"S 107°44'6.900"E   | 107.73525000000001 |  -7.064750000000001
7°3'51.300"S 107°44'6.900"E   | 107.73525000000001 |            -7.06425
7°3'49.500"S 107°44'6.900"E   | 107.73525000000001 |  -7.063750000000001
7°3'47.700"S 107°44'6.900"E   | 107.73525000000001 |  -7.063250000000001
7°3'45.900"S 107°44'6.900"E   | 107.73525000000001 |            -7.06275
```
