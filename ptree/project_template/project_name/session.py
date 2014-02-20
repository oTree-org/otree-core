import ptree.session

def create(name):
    return ptree.session.create(
        label='',
        base_pay=0,
        is_for_mturk=False,
        num_participants=30,
        subsession_names= ['myapp']
    )