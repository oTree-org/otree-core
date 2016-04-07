from channels import Group


def connect_wait_page(message, group_name):
    group = Group('wait_page_{}'.format(group_name))
    group.add(message.reply_channel)


def disconnect_wait_page(message, group_name):
    group = Group('wait_page_{}'.format(group_name))
    group.discard(message.reply_channel)


def connect_auto_advance(message, participant_code):
    group = Group('auto_advance_{}'.format(participant_code))
    group.add(message.reply_channel)


def disconnect_auto_advance(message, participant_code):
    group = Group('auto_advance_{}'.format(participant_code))
    group.discard(message.reply_channel)

