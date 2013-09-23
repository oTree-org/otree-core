Prerequisites
*************

Before getting started with pTree, you need the following.

Command line
============
You need a basic understanding of what a command prompt is and how to use it.
You should know basic comamnds like ``ls``, ``cd``, and ``mv``.

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
You will write your pTree apps in `Python <http://www.python.org/>`__.

Python is an easy-to-learn yet powerful and versatile programming language.
It is very popular and has a great ecosystem of tutorials, libraries, and tools.

Learning
---------------

You must have intermediate knowledge of Python to use pTree.
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

Installation
------------
Install `Python <http://www.python.org/>`__ version 2.7 (not 3.X).

You will also need an editor to write your Python code.
Although you can use any text editor you want,
I find it is much easier to create pTree apps in an IDE
that has features like code completion, error detection,
and easy navigation between the many modules and classes in your project.

Here are some popular IDEs:

- `Python Tools for Visual Studio <https://pytools.codeplex.com/wikipage?title=PTVS%20Installation>`__ (Windows only); just make sure to follow the instructions on how to download the free version.
- `PyDev for Eclipse <http://pydev.org/>` (Windows/Mac/Linux)
- `Komodo Edit <http://www.openkomodo.com/>`__ (Windows/Mac/Linux)
- `PyCharm <http://www.jetbrains.com/pycharm/>`__ (Windows/Mac/Linux) (not free)
- `Sublime Text 2 <http://www.sublimetext.com/>`__ (Windows/Mac/Linux) (not free)


Pip
===
You will need `Pip <http://www.pip-installer.org/en/latest/installing.html>`_ to install packages.
Install it and make sure you can run commands like ``pip install django-ptree`` from your command line.

Django
======
pTree is built on top of Django, 
which is the most popular web development framework for Python.

In the process of learning and using pTree, you will learn some Django.
To understand the core concepts of Django (and pTree),
go to `this page of the Django book <http://www.djangobook.com/en/2.0/chapter01.html>`__ 
and read until the end of the section "The MVC design pattern".

When you install pTree, Django will get installed automatically.