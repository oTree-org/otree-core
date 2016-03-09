from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
)

import otree.urls
urlpatterns += otree.urls.urlpatterns()
