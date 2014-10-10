from django.conf.urls import patterns
import otree.urls
from otree.adminlib import autodiscover

autodiscover()

urlpatterns = patterns('',)

otree.urls.augment_urlpatterns(urlpatterns)
