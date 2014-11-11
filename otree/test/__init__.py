from importlib import import_module

#==============================================================================
# DOC
#==============================================================================

"""OTree test framework

"""

# NOTE: this imports the following submodules and then subclasses several
# classes importing is done via import_module rather than an ordinary import.
#
# The only reason for this is to hide the base classes from IDEs like PyCharm,
# so that those members/attributes don't show up in autocomplete,
# including all the built-in django fields that an ordinary oTree programmer
# will never need or want. if this was a conventional Django project I wouldn't
# do it this way, but because oTree is aimed at newcomers who may need more
# assistance from their IDE, I want to try this approach out.
#
# This module is also a form of documentation of the public API.

#==============================================================================
# IMPORTS
#==============================================================================

client = import_module('otree.test.client')


#==============================================================================
# CLIENTS
#==============================================================================

class Bot(client.PlayerBot):

    def play(self):
        return super(Bot, self).play()

    def submit(self, ViewClass, param_dict=None):
        return super(Bot, self).submit(ViewClass, param_dict)

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        return super(Bot, self).submit_with_invalid_input(
            ViewClass, param_dict
        )


class ExperimenterBot(client.ExperimenterBot):

    def play(self):
        return super(ExperimenterBot, self).play()

    def submit(self, ViewClass, param_dict=None):
        return super(ExperimenterBot, self).submit(ViewClass, param_dict)

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        return super(ExperimenterBot, self).submit_with_invalid_input(
            ViewClass, param_dict
        )
