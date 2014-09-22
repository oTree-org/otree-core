from django.conf.urls import include, patterns, url


urlpatterns = patterns('',
    url(r'^$', 'tests.demo.views.index', name='index'),
    url(r'^widgets/', 'tests.demo.views.widgets', name='widgets'),
)
