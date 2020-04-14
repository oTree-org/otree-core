
How to
~~~~~~~~~~~~~~
Use following methodology when git cloning the project:
::

    pip install -e .
    pip install -r requirements.txt
    cd otree
    cd oTree
    otree devserver
 
How to log into the system as an admin:
::

    Create an admin/superuser with the following commands in your terminal:
    # otree createsuperuser
        Log in with this admin login and enter the admin panel with the URL:
    /admin/
    
    IF you are using shellbash and getting an error when creating a super user, try to use the following command:
::
    winpty python manage.py createsuperuser
    

