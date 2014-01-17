import ptree.session.models

def create_session(name):
    ptree.session.models.create_session(label='',
                    base_pay=0,
                    is_for_mturk=False,
                    preassign_matches=True,
                    num_participants=30,
                    app_names = ['myapp'])