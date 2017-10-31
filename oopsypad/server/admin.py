import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import jsonify, request
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.mongoengine import ModelView
from flask_admin.model.template import macro
import random

from oopsypad.server.helpers import last_12_months
from oopsypad.server import models


def get_random_color():
    return "#%06x" % random.randint(0, 0xFFFFFF)


def get_decorated_data(labels, data, data_labels=None):
    result = {'labels': labels}
    datasets = []
    for i, d in enumerate(data):
        clr = get_random_color()
        ds = {
            'fillColor': clr,
            'strokeColor': clr,
            'highlightFill': clr,
            'highlightStroke': "rgba(220,220,220,1)",
            'data': d
        }
        if data_labels:
            ds.update({'label': data_labels[i]})

        datasets.append(ds)
    result['datasets'] = datasets
    return result


def get_last_12_months_labels():
    today = datetime.now()
    labels = [(today - relativedelta(months=months)).month for months in last_12_months()]
    return [calendar.month_name[m] for m in labels]


class CustomAdminView(AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')


class ProjectView(ModelView):
    action_disallowed_list = ['delete']
    can_view_details = True
    column_display_actions = False
    column_editable_list = ['name']
    column_formatters = dict(actions=macro('render_actions'))
    column_list = ('name', 'actions')
    create_modal = True
    create_modal_template = 'admin/add_project_modal.html'
    create_template = 'admin/add_project.html'
    edit_template = 'admin/edit_project.html'
    form_args = {
        'min_version': {'label': 'Minimum required version of crashed app'},
        'allowed_platforms': {'label': 'Allowed platforms'}
    }
    form_create_rules = {'name'}
    form_edit_rules = ('min_version', 'allowed_platforms')
    list_template = '/admin/project_list.html'

    @expose('/details/')
    def details_view(self):
        project = models.Project.objects.get(id=request.args.get('id'))
        project_minidumps = models.Minidump.objects(product=project.name)
        minidump_versions = models.Minidump.get_versions_per_product(product=project.name)
        last_10_minidumps = project_minidumps.order_by('-date_created')[:10]
        return self.render('admin/project_overview.html',
                           project=project,
                           versions=minidump_versions,
                           latest_crash_reports=last_10_minidumps,
                           top_issues=[]  # TODO: replace with actual data
                           )

    @expose('/_crash_reports')
    def crash_reports_chart(self):
        version = request.args.get('version')
        project = models.Project.objects.get(id=request.args.get('id'))
        platforms = project.get_allowed_platforms()
        if version and 'All' not in version:
            project_minidumps = models.Minidump.objects(product=project.name, version=version)
        else:
            project_minidumps = models.Minidump.objects(product=project.name)
        data = {}
        for platform in platforms:
            platform_minidumps = project_minidumps(platform=platform)
            data[platform] = models.Minidump.get_last_12_months_minidumps_count(platform_minidumps)
        labels = get_last_12_months_labels()

        return jsonify(
            result=get_decorated_data(labels=labels,
                                      data=data.values(),
                                      data_labels=list(data.keys())
                                      ))


class CrashReportView(ModelView):
    column_list = ('product', 'version', 'platform', 'date_created', 'crash_reason')
    column_filters = ('product', 'version', 'platform', 'date_created', 'crash_reason')
    list_template = 'admin/crash_report_list.html'


admin = Admin(
    name='OopsyPad',
    template_mode='bootstrap3',
    index_view=CustomAdminView(
        template='index.html',
        url="/")
)

admin.add_view(ProjectView(models.Project, name='Projects'))
admin.add_view(ModelView(models.Platform, name='Platforms'))
admin.add_view(CrashReportView(models.Minidump, name='Crash Reports', endpoint='crash-reports'))