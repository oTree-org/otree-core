from django.shortcuts import render_to_response
from django.template import RequestContext

from .forms import WidgetDemoForm


def index(request):
    return render_to_response('demo/index.html', {
    }, context_instance=RequestContext(request))


def widgets(request):
    if request.method == 'POST':
        form = WidgetDemoForm(request.POST, request.FILES)
    else:
        form = WidgetDemoForm()

    return render_to_response('demo/widgets.html', {
        'form': form,
    }, context_instance=RequestContext(request))
