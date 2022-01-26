# Setting up a development environment

1. Clone this repository, open a terminal and cd to the repository root.
2. Install conda (I recommend [miniconda](https://docs.conda.io/en/latest/miniconda.html) if you don't have conda installed).
3. Install and activate the ManyFEWS conda environment:

   ```bash
   $ conda env create --file condaEnv/manyFEMSenv.yml
   $ conda activate ManyFEWS
   ```

4. Install postgres 14 and PostGIS (see https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/postgis/)
5. Create a `manyfews` user and database and enable the PostGIS extension:

   ```bash
   $ createuser manyfews --createdb --pwprompt
   Enter password for new role: manyfews
   Enter it again: manyfews
   $ createdb manyfews -O manyfews
   $ psql manyfews
   > CREATE EXTENSION postgis;
   ```

6. Run the django app in development mode:

   ```
   cd manyfews
   python manage.py runserver
   ```

   Go to http://127.0.0.1:8000/webapp/ and check that your app works.
