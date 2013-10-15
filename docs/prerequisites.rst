Prerequisites
*************

Command line
============

You need a basic understanding of your operating system's command prompt.
You should know common commands like ``ls``, ``cd``, and ``mv``,
and how to launch a program by entering its name at the command prompt.
Here is how to open your command prompt.

Windows
-------

- Click Start.
- In "Search programs and files" type: powershell
- Hit Enter.

Mac OSX
-------

- Hold down COMMAND and hit the spacebar.
- In the top right the blue "search bar" will pop up.
- Type: terminal
- Click on the Terminal application that looks kind of like a black box.
- This will open Terminal.
- You can now go to your Dock and CTRL-click to pull up the menu, then select Options->Keep In Dock.

Python
======

You will write your ptree apps in `Python <http://www.python.org/>`__.

Python is an easy-to-learn yet powerful and versatile programming language.
It is very popular and has a great ecosystem of tutorials, libraries, and tools.

Installation
------------

Python interpreter
~~~~~~~~~~~~~~~~~~

Install `Python <http://www.python.org/>`__ version 2.7 (not 3.X).

Pip
~~~

You will need a program called Pip in order to install packages.

Download `ez_setup.py <https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py>`__,
then run the following command with administrator privileges
(on Windows, right-click the Windows PowerShell app icon, then click "Run as administrator".)::

	python ez_setup.py

Then, download `get-pip.py <https://raw.github.com/pypa/pip/master/contrib/get-pip.py>`__,
and run it (again with administrator privileges) as follows::

	python get-pip.py
	
To verify that it is correctly installed, try the command ``pip install requests`` from your command line.

Editor
~~~~~~

Install `PyCharm <http://www.jetbrains.com/pycharm/>`__.

I recommend installing the free 30-day trial of the Professional Edition,
since it has features that make Django development much easier,
and thus ease the learning curve of ptree.

After 30 days, you can either get a free Classroom License
(as explained `here <http://www.jetbrains.com/pycharm/buy/index.jsp>`__),
or downgrade to the free Community Edition, 
or buy an Academic License for $29.

.. note::

	You can use any Python editor you want,
	but this documentation gives instructions assuming you are using PyCharm,
	
Learning
=========

You must have intermediate knowledge of Python to use ptree.
You should at least understand the basics of procedural and object-oriented programming: 
control structures (e.g., if, while, for), 
data structures (lists, hashes/dictionaries), 
variables, classes and objects.

If you have programmed before in another programming language like Java, C#, C++, or Ruby,
Python will be very easy for you to pick up.
Experience with scientific languages like R, Matlab, or Stata can also help,
but there will be more new concepts to learn.

If you need to learn Python, there are many good tutorials on the web you can choose from, such as:

- The `Codecademy <http://www.codecademy.com/tracks/python>`__ interactive tutorial that runs in your browser.
- `Learn Python the Hard Way <http://learnpythonthehardway.org/book/>`_. (Work your way up through Exercise 41: "Learning to Speak Object Oriented". You can skip Exercises 11-17.)

