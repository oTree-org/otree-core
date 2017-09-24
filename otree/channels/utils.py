def create_session_group_name(pre_create_id):
    return 'wait_for_session_{}'.format(pre_create_id)


def wait_page_group_name(session_pk, page_index,
                         group_id_in_subsession=''):

    return 'wait-page-{}-page{}-{}'.format(
        session_pk, page_index, group_id_in_subsession)


def gbat_group_name(session_pk, page_index):
    return 'group_by_arrival_time_session{}_page{}'.format(
        session_pk, page_index)

def gbat_path(session_id, index_in_pages, app_name, player_id):
    return '/group_by_arrival_time/{},{},{},{}/'.format(
        session_id, index_in_pages, app_name, player_id
        )

def room_participants_group_name(room_name):
    return 'room-participants-{}'.format(room_name)


def room_participant_path(room_name, participant_label, tab_unique_id):
    return '/wait_for_session_in_room/{},{},{}/'.format(
            room_name, participant_label, tab_unique_id
    )

def room_admin_path(room_name):
    return '/room_without_session/{}/'.format(room_name)

def wait_for_session_path(pre_create_id):
    return '/wait_for_session/{}/'.format(pre_create_id)

def wait_page_path(session_pk, index_in_pages, group_id_in_subsession):
    return '/wait_page/{},{},{}/'.format(
        session_pk, index_in_pages, group_id_in_subsession
    )