import ptree.session

#FIXME: this needs to change to the new SessionType format
def create(name):
    return ptree.session.create(
        label='',
        base_pay=0,
        num_participants=3,
        subsession_names= ['myapp']
    )