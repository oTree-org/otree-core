from django.conf.urls import *
import ptree.urls
from django.contrib import admin


admin.autodiscover()

urlpatterns = patterns('',)

ptree.urls.augment_urlpatterns(urlpatterns)