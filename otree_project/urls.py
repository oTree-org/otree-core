from django.conf.urls import patterns, include, url

urlpatterns = patterns('',

    # Examples:
    # url(r'^$', 'django_otree.views.home', name='home'),
    # url(r'^django_otree/', include('django_otree.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

import otree.urls
urlpatterns += otree.urls.urlpatterns()
