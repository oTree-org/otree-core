# CW 2014-10-3: renamed this module from otree to otree_tags because "import otree" was importing this module instead of top-level otree module
from __future__ import unicode_literals
import datetime
import json
import urllib

from django.conf import settings
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.util import (lookup_field, display_for_field,
    display_for_value, label_for_field)
from django.contrib.admin.views.main import (ALL_VAR, EMPTY_CHANGELIST_VALUE,
    ORDER_VAR, PAGE_VAR, SEARCH_VAR)
from django.contrib.admin.templatetags import admin_list
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import escapejs, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.template import Library

from ..db import models


DOT = '.'

register = Library()

@register.inclusion_tag('admin/ajax_pagination.html')
def ajax_pagination(cl):
    """
    Generates the series of links to the pages in a paginated list.
    """
    paginator, page_num = cl.paginator, cl.page_num

    pagination_required = (not cl.show_all or not cl.can_show_all) and cl.multi_page
    if not pagination_required:
        page_range = []
    else:
        ON_EACH_SIDE = 3
        ON_ENDS = 2

        # If there are 10 or fewer pages, display links to every page.
        # Otherwise, do some fancy
        if paginator.num_pages <= 10:
            page_range = range(paginator.num_pages)
        else:
            # Insert "smart" pagination links, so that there are always ON_ENDS
            # links at either end of the list of pages, and there are always
            # ON_EACH_SIDE links at either end of the "current page" link.
            page_range = []
            if page_num > (ON_EACH_SIDE + ON_ENDS):
                page_range.extend(range(0, ON_ENDS))
                page_range.append(admin_list.DOT)
                page_range.extend(range(page_num - ON_EACH_SIDE, page_num + 1))
            else:
                page_range.extend(range(0, page_num + 1))
            if page_num < (paginator.num_pages - ON_EACH_SIDE - ON_ENDS - 1):
                page_range.extend(range(page_num + 1, page_num + ON_EACH_SIDE + 1))
                page_range.append(admin_list.DOT)
                page_range.extend(range(paginator.num_pages - ON_ENDS, paginator.num_pages))
            else:
                page_range.extend(range(page_num + 1, paginator.num_pages))

    need_show_all_link = cl.can_show_all and not cl.show_all and cl.multi_page
    return {
        'cl': cl,
        'pagination_required': pagination_required,
        'show_all_url': need_show_all_link and cl.get_query_string({ALL_VAR: ''}),
        'page_range': page_range,
        'ALL_VAR': ALL_VAR,
        '1': 1,
    }

def result_headers(cl):
    """
    Generates the list column headers.
    """
    ordering_field_columns = cl.get_ordering_field_columns()
    for i, field_name in enumerate(cl.list_display):
        text, attr = label_for_field(field_name, cl.model,
            model_admin = cl.model_admin,
            return_attr = True
        )
        if attr:
            # Potentially not sortable

            # if the field is the action checkbox: no sorting and special class
            if field_name == 'action_checkbox':
                yield {
                    "text": text,
                    "class_attrib": mark_safe(' class="action-checkbox-column"'),
                    "sortable": False,
                }
                continue

            admin_order_field = getattr(attr, "admin_order_field", None)
            if not admin_order_field:
                # Not sortable
                yield {
                    "text": text,
                    "class_attrib": format_html(' class="column-{0}"', field_name),
                    "sortable": False,
                }
                continue

        # OK, it is sortable if we got this far
        th_classes = ['sortable', 'column-{0}'.format(field_name)]
        order_type = ''
        new_order_type = 'asc'
        sort_priority = 0
        sorted = False
        # Is it currently being sorted on?
        if i in ordering_field_columns:
            sorted = True
            order_type = ordering_field_columns.get(i).lower()
            sort_priority = list(ordering_field_columns).index(i) + 1
            th_classes.append('sorted %sending' % order_type)
            new_order_type = {'asc': 'desc', 'desc': 'asc'}[order_type]

        # build new ordering param
        o_list_primary = [] # URL for making this field the primary sort
        o_list_remove  = [] # URL for removing this field from sort
        o_list_toggle  = [] # URL for toggling order type for this field
        make_qs_param = lambda t, n: ('-' if t == 'desc' else '') + str(n)

        for j, ot in ordering_field_columns.items():
            if j == i: # Same column
                param = make_qs_param(new_order_type, j)
                # We want clicking on this header to bring the ordering to the
                # front
                o_list_primary.insert(0, param)
                o_list_toggle.append(param)
                # o_list_remove - omit
            else:
                param = make_qs_param(ot, j)
                o_list_primary.append(param)
                o_list_toggle.append(param)
                o_list_remove.append(param)

        if i not in ordering_field_columns:
            o_list_primary.insert(0, make_qs_param(new_order_type, i))


        yield {
            "text": text,
            "sortable": True,
            "sorted": sorted,
            "ascending": order_type == "asc",
            "sort_priority": sort_priority,
            "url_primary": cl.get_query_string({ORDER_VAR: '.'.join(o_list_primary)}),
            "url_remove": cl.get_query_string({ORDER_VAR: '.'.join(o_list_remove)}),
            "url_toggle": cl.get_query_string({ORDER_VAR: '.'.join(o_list_toggle)}),
            "class_attrib": format_html(' class="{0}"', ' '.join(th_classes))
                            if th_classes else '',
        }

def wrap_in_div(text):
    return ('<div class="cell-trunc-div" '
            'style="clear: both; height: 1.2em;'
            ' overflow: hidden; white-space: nowrap;">%s</div>' % (text, ))
    #return text

def items_for_result(cl, result, form):
    """
    Generates the actual list of data.
    """
    first = True
    pk = cl.lookup_opts.pk.attname
    for field_idx in range(len(cl.list_display)):
        field_name = cl.list_display[field_idx]
        is_last = (field_idx == len(cl.list_display) - 1)
        if is_last:
            extra_class = ' last_cell '
        else:
            extra_class = ' '
        row_class = '' + extra_class
        at = False
        try:
            f, attr, value = lookup_field(field_name, result, cl.model_admin)
        except ObjectDoesNotExist:
            result_repr = EMPTY_CHANGELIST_VALUE
        except:
            result_repr = "(Error)"
        else:
            if f is None:
                if field_name == 'action_checkbox':
                    row_class = mark_safe(' class="action-checkbox"')
                at = allow_tags = getattr(attr, 'allow_tags', False)
                boolean = getattr(attr, 'boolean', False)
                if boolean:
                    allow_tags = True
                result_repr = display_for_value(value, boolean)
                # Strip HTML tags in the resulting text, except if the
                # function has an "allow_tags" attribute set to True.
                if allow_tags:
                    result_repr = mark_safe(result_repr)
                if isinstance(value, (datetime.date, datetime.time)):
                    row_class = mark_safe(' class="nowrap"')
            else:
                if isinstance(f.rel, models.ManyToOneRel):
                    field_val = getattr(result, f.name)
                    if field_val is None:
                        result_repr = EMPTY_CHANGELIST_VALUE
                    else:
                        result_repr = field_val
                else:
                    result_repr = display_for_field(value, f)
                if isinstance(f, (models.DateField, models.TimeField, models.ForeignKey)):
                    row_class = mark_safe(' class="nowrap"')
        if force_text(result_repr) == '':
            result_repr = mark_safe('&nbsp;')
        # If list_display_links not defined, add the link tag to the first field
        if (first and not cl.list_display_links) or field_name in cl.list_display_links:
            table_tag = {True:'th', False:'td'}[first]
            first = False
            url = cl.url_for_result(result)
            url = add_preserved_filters({'preserved_filters': cl.preserved_filters, 'opts': cl.opts}, url)
            # Convert the pk to something that can be used in Javascript.
            # Problem cases are long ints (23L) and non-ASCII strings.
            if cl.to_field:
                attr = str(cl.to_field)
            else:
                attr = pk
            value = result.serializable_value(attr)
            result_id = escapejs(value)
            yield format_html('<{0}{1}>' + wrap_in_div('<a href="{2}"{3}>{4}</a>') + '</div></{5}>',
                              table_tag,
                              row_class,
                              url,
                              format_html(' onclick="opener.dismissRelatedLookupPopup(window, &#39;{0}&#39;); return false;"', result_id)
                                if cl.is_popup else '',
                              result_repr,
                              table_tag)
        else:
            # By default the fields come from ModelAdmin.list_editable, but if we pull
            # the fields out of the form instead of list_editable custom admins
            # can provide fields on a per request basis
            if (form and field_name in form.fields and not (
                    field_name == cl.model._meta.pk.name and
                        form[cl.model._meta.pk.name].is_hidden)):
                bf = form[field_name]
                result_repr = mark_safe(force_text(bf.errors) + force_text(bf))
            yield format_html('<td{0}>' + wrap_in_div('{1}') + '</div></td>', row_class, result_repr)
    if form and not form[cl.model._meta.pk.name].is_hidden:
        val_txt = force_text(form[cl.model._meta.pk.name])
        yield format_html('<td>' + wrap_in_div('{0}') + '</div></td>', val_txt)

class ResultList(list):
    # Wrapper class used to return items in a list_editable
    # changelist, annotated with the form object for error
    # reporting purposes. Needed to maintain backwards
    # compatibility with existing admin templates.
    def __init__(self, res, form, *items):
        self.res = res
        self.form = form
        super(ResultList, self).__init__(*items)

def results(cl):
    if cl.formset:
        for res, form in zip(cl.result_list, cl.formset.forms):
            yield ResultList(res, form, items_for_result(cl, res, form))
    else:
        for res in cl.result_list:
            yield ResultList(res, None, items_for_result(cl, res, None))

def result_hidden_fields(cl):
    if cl.formset:
        for res, form in zip(cl.result_list, cl.formset.forms):
            if form[cl.model._meta.pk.name].is_hidden:
                yield mark_safe(force_text(form[cl.model._meta.pk.name]))


def prepare_results_json(cl):
    the_results = list(results(cl))
    results_map = dict([(result.res.pk, [cell for cell in result]) for result in the_results])
    result_ids = [str(result.res.pk) for result in the_results]
    return the_results, json.dumps({"results_map": results_map, "results_ids": result_ids})

@register.inclusion_tag("admin/otree_change_list_results.html")
def ajax_result_list(cl, request):
    """
    Displays the headers and data list together
    """
    get_params_str = urllib.urlencode(request.GET)
    print get_params_str
    headers = []
    for header in result_headers(cl):
        headers.append(header)
    num_sorted_fields = 0
    for h in headers:
        if h['sortable'] and h['sorted']:
            num_sorted_fields += 1

    the_results, results_json = prepare_results_json(cl)
    # TODO: results_json
    return {'cl': cl,
            'settings': settings,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': headers,
            'num_sorted_fields': num_sorted_fields,
            'url_name': json.dumps(request.resolver_match.url_name),
            'results_json': results_json,
            'get_params_str': json.dumps(get_params_str),
            'results': the_results}


@register.inclusion_tag('admin/ajax_actions.html', takes_context=True)
def ajax_admin_actions(context):
    """
    Track the number of times the action field has been rendered on the page,
    so we know which value to use.
    """
    context['action_index'] = context.get('action_index', -1) + 1
    return context

