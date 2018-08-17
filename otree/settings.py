#from otree_setup.settings import augment_settings

def augment_settings(*args, **kwargs):
    '''don't need this, now that we do it in otree-core'''
    pass

# eventually, make augment_settings raise an error.
# users should instead directly use otree_startup.augment_settings

