from django.template import Library
from ptree import common


register = Library()


EXPERIMENT_APP_MODELS_ORDER = ["Experiment", "Treatment", "Match", "Participant"]


def _get_model_position(object_name):
    try:
        position = EXPERIMENT_APP_MODELS_ORDER.index(object_name)
    except ValueError:
        position = -1
    return position


def fix_experiment_app_models_order(models):
    models = [model for model in models]
    models.sort(lambda a, b: cmp(_get_model_position(a["object_name"]), _get_model_position(b["object_name"])))
    return models


def is_experiment_app(app):
    return common.is_experiment_app(app["app_label"])


def experiment_apps_only(apps):
    return [app for app in apps if common.is_experiment_app(app["app_label"])]


def non_experiment_apps(apps):
    return [app for app in apps if not common.is_experiment_app(app["app_label"])]

register.filter('fix_experiment_app_models_order', fix_experiment_app_models_order)
register.filter('experiment_apps_only', experiment_apps_only)
register.filter('non_experiment_apps', non_experiment_apps)
register.filter('app_name_format', common.app_name_format)
