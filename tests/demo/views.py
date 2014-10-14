from django.template.response import TemplateResponse
from django.template import RequestContext

from .forms import WidgetDemoForm


def index(request):
    return TemplateResponse(request, 'demo/index.html', {
    }, context_instance=RequestContext(request))


def widgets(request):
    if request.method == 'POST':
        form = WidgetDemoForm(request.POST, request.FILES)
    else:
        form = WidgetDemoForm()

    return TemplateResponse(request, 'demo/widgets.html', {
        'form': form,
    })
