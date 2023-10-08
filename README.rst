`Homepage`_

These are the core oTree libraries.

Before you fork this project, keep in mind that otree is updated
frequently, and over time you might get upstream merge conflicts, as
your local project diverges from the oTree mainline version.

Instead, consider creating a project with ``otree startproject`` and
making your modifications in an app, using oTree’s public API. You can
create custom URLs, channels, override settings, etc.

Docs
----

http://otree.readthedocs.io/en/latest/index.html

Quickstart
----------

Typical setup
~~~~~~~~~~~~~

::

    pip install -U otree
    otree startproject oTree
    cd oTree
    otree devserver

Core dev setup
~~~~~~~~~~~~~~

If you are modifying otree-core locally, clone or download this repo,
then run this from the project root:

::

    pip install -e .
    cd .. # or wherever you will start your project
    otree startproject oTree
    cd oTree
    otree devserver

i18n
~~~~

To generate .pot and update .po files::

    cd tests
    pybabel extract "../otree" -o "../otree/locale/django.pot" -F "..\otree\locale\babel.ini" -k core_gettext -c Translators:
    cd ..
    pybabel update -D django -i otree/locale/django.pot -d otree/locale

To compile .po to .mo::

    pybabel compile -d otree/locale -f -D django

Note, beware of the issue
`here <https://github.com/python-babel/babel/issues/665>`__

To add a new language (e.g. Polish)::

    pybabel init -D django -i otree/locale/django.pot -d otree/locale -l pl

.. _Homepage: http://www.otree.org/
