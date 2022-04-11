# Scheduling tasks using celery

The following tasks should be scheduled daily, allowing time for each task to complete before running the next (time will depend on the server the code is running on):

1. Generate river flows
2. Run flood model
3. Calculate risk percentages

Scheduling can be done using the admin interface at http://127.0.0.1:8000/admin.

1. Log in as an admin user.
2. Go to **Periodic tasks** and click "Add".
3. Give the task a name.
4. Choose the job to run (e.g. `Run flood model`).
5. Next to "Crontab Schedule" click the + button.
6. Fill in the values for the crontab, eg. to run every day at 2am, choose minutes 0, hour 2, and leave the rest as *. Click Save.
7. Choose the start datetime (use the Today and Now links to start immediately).
8. Click save.

Repeat for the other tasks.
