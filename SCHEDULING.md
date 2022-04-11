# Scheduling tasks using celery

Scheduled tasks are run using [celery](https://docs.celeryproject.org/en/stable/index.html), but can be set up using the Django admin interface at at http://127.0.0.1:8000/admin.

When setting up a new server you need to:

1. Run the "calculations.initialModelSetUp" task once. (TODO: check how to do that with admin interface).
2. Set up daily scheduled tasks.


## 1. Initial model setup

1. Go to http://127.0.0.1:8000/admin and log in as an admin user.
2. Go to **Periodic tasks** and click "Add".
3. Give the task a name, e.g. "Initial setup".
4. Under **Task (registered)** choose "calculations.initialModelSetUp".
5. Next to **Clocked Schedule** click the + button.
6. Choose the time to start the job (use the Today and Now links to start immediately).
8. Click **Save**.

The initial model should run. You can check the celery logs for details.

## 2. Daily tasks

The following tasks should be scheduled daily, allowing time for each task to complete before running the next. (The time needed will depend on the server the code is running on: set up each task and see how long it takes before setting up the next.)

1. calculations.dailyModelUpdate
2. Run flood model (depends on dailyModelUpdate)
3. Calculate risk percentages (depends on 'Run flood model', which has many subtasks)
4. Send all alerts (depends on 'Run flood model', which has many subtasks)

To schedule each task:

1. Go to http://127.0.0.1:8000/admin and log in as an admin user.
2. Go to **Periodic tasks** and click "Add".
3. Give the task a name.
4. Choose the job to run (e.g. 'Run flood model').
5. Next to **Crontab Schedule** click the + button.
6. Fill in the values for the crontab, eg. to run every day at 2am, choose minutes 0, hour 2, and leave the rest as *. Click Save.
7. Choose the start datetime (use the Today and Now links to start immediately).
8. Click **Save**.

Repeat for the other tasks.
