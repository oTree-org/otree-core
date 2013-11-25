#!/usr/bin/env python
# standalone script to be run from the shell as "./recreate_environment.py [arg]",
# where [arg] is local (for your development machine),
# or dev/staging/production (for Heroku)
# use this when you've made changes to the code that affected the database schema.
# it will drop the dev DB and recreate it, thus providing a blank slate.

import sys
import os
import copy_ptree
import commit_and_push
import sys

def main():
    environment = sys.argv[1]
    num_participants = 50
    app_name = 'your_app_name_here'

    syncdb = 'python manage.py syncdb'
    create_objects = 'python manage.py create_objects --app_name={} --participants={}'.format(app_name,
                                                                                   num_participants)

    if environment == 'local':
        open('ptree_experiments/db.sqlite3', 'w').write('')
        os.system(syncdb)
        os.system(create_objects)
        # then launch from PyCharm
    else: # heroku
        if environment == 'production':
            confirmed = raw_input('Enter "y" to confirm deletion of your production database').lower() == 'y'
            if not confirmed:
                sys.exit(0)

        # replace the below app names with your heroku app names
        heroku_apps = {'dev': 'heroku-app-name-dev',
                       'staging': 'heroku-app-name-staging',
                       'production': 'heroku-app-name-production'}

        reset_db = 'heroku pg:reset DATABASE --confirm {}'.format(heroku_apps[environment])
        os.system(reset_db)

        commit_and_push.run(environment)

        heroku_run_command = 'heroku run {} --remote {}'
        syncdb = heroku_run_command.format(syncdb, environment)
        create_objects = heroku_run_command.format(create_objects, environment)

        os.system(syncdb)
        os.system(create_objects)

if __name__ == '__main__':
    main()