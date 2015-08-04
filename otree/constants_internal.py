#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

from django.db import utils
from django.utils.translation import ugettext_lazy

# =============================================================================
# CONSTANTS
# =============================================================================

SubsessionClass = 'SubsessionClass'
GroupClass = 'GroupClass'
PlayerClass = 'PlayerClass'
UserClass = 'UserClass'

group_id = 'group_id'

user_code = 'user_code'
subsession_code = 'subsession_code'
subsession_code_obfuscated = 'exp_code'

nickname = 'nickname'

completed_views = 'completed_views'

form_invalid = 'form_invalid'
precondition = 'precondition'
mturk_worker_id = 'mturk_worker_id'
debug_values_built_in = 'debug_values_built_in'
debug_values = 'debug_values'
check_if_wait_is_over = 'check_if_wait_is_over'
get_param_truth_value = '1'
admin_access_code = 'admin_access_code'
index_in_pages = 'index_in_pages'

timeout_seconds = 'timeout_seconds'
auto_submit = 'auto_submit'
check_auto_submit = 'check_auto_submit'
page_expiration_times = 'page_timeouts'
participant_label = 'participant_label'
session_user_id = 'session_user_id'
session_user_code = 'session_user_code'
session_id = 'session_id'
session_code = 'session_code'
wait_page_http_header = 'oTree-Wait-Page'
redisplay_with_errors_http_header = 'oTree-Redisplay-With-Errors'
user_type = 'user_type'
user_type_participant = 'p'
success = True
failure = False
session_special_category_bots = 'bots'
session_special_category_demo = 'demo'
access_code_for_default_session = 'access_code_for_default_session'

form_page_poll_interval_seconds = 5
wait_page_poll_interval_seconds = 10

exceptions_conversors = {
    utils.OperationalError: lambda exception: utils.OperationalError(
        "{} - Try resetting the database.".format(exception.message)
    )
}

# Translators: for required form fields
field_required_msg = ugettext_lazy('This field is required.')
