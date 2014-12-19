import os
import platform
import subprocess
import sys
import django.core.management


def execute_from_command_line(arguments, script_file):
    # Workaround for windows. Celery (more precicely the billard library) will
    # complain if the script you are using to initialize celery does not end
    # on '.py'. That's why we require a manage.py file to be around.
    # See https://github.com/celery/billiard/issues/129 for more details.
    if platform.system() == 'Windows' and not script_file.lower().endswith('.py'):

        scriptdir = os.path.dirname(os.path.abspath(script_file))
        managepy = os.path.join(scriptdir, 'manage.py')
        if not os.path.exists(managepy):
            sys.stderr.write(
                "It seems that you do not have a file called 'manage.py' next "
                "to the ./otree script you just called. This is a requirement "
                "when using otree on windows.")
            sys.stderr.write("\n\n")
            sys.stderr.write(
                "Please download the file {url} and save it as 'manage.py' in "
                "the directory {directory}".format(
                    url="https://raw.githubusercontent.com/oTree-org/oTree/master/manage.py",
                    directory=scriptdir))
            sys.exit(1)
        args = [sys.executable] + [managepy] + sys.argv[1:]
        process = subprocess.Popen(args,
                                   stdin=sys.stdin,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr)
        return_code = process.wait()
        sys.exit(return_code)

    django.core.management.execute_from_command_line(sys.argv)
