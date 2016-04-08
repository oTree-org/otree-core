from channels import Group


def connect_wait_page(message, group_name):
    group = Group('wait_page_{}'.format(group_name))
    group.add(message.reply_channel)


def disconnect_wait_page(message, group_name):
    group = Group('wait-page-{}'.format(group_name))
    group.discard(message.reply_channel)


def connect_auto_advance(message, participant_code):
    group = Group('auto-advance-{}'.format(participant_code))
    group.add(message.reply_channel)


def disconnect_auto_advance(message, participant_code):
    group = Group('auto-advance-{}'.format(participant_code))
    group.discard(message.reply_channel)

'''
def connect_admin_lobby(message):

    Group('admin_lobby').add(message.)
    ids = ParticipantVisit.objects.all()
    Group('admin_lobby').send(ids)


def connect_participant_lobby(message):

    ParticipantVisit(participant_id).save()
    Group('admin_lobby').send({'participant': participant_id})

def disconnect_participant_lobby(message):

    Group('admin_lobby').send({'participant': participant_id, 'action': 'Leaving'})
    ParticipantVisit(participant_id).delete()
'''