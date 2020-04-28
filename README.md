
## How to run KU-Læringsspil

### Use following methodology when git cloning the project:

```
    cd otree-core
    pip install -e .
    pip install -r requirements.txt
    cd otree
    cd oTree
    otree devserver
```

### How to log into the system as an admin:

Create an admin/superuser with the following commands in your terminal:
```
    otree createsuperuser
    otree devserver
```
Log in via. login button on the front page /spil/

OR

Log in with the admin login and enter the admin panel with the URL:

/admin/


IF you are using shellbash and getting an error when creating a super user, try to use the following command:

```
    winpty python manage.py createsuperuser
```

<!--
How to log into the system as a player:

    To log in as a player:
       1. create a session/game
       2. go to the admin panel and choose a player username
       3. then log into the system with the username and the password: 123456
-->
