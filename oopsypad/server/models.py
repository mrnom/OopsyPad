from datetime import datetime
from dateutil.relativedelta import relativedelta
import mongoengine as mongo
from mongoengine import fields
from mongoengine.queryset.visitor import Q
import os
from werkzeug.utils import secure_filename

from oopsypad.server.helpers import last_12_months

DUMPS_DIR = "dumps"
SYMFILES_DIR = "symbols"


class Minidump(mongo.Document):
    # product version platform upload_file_minidump
    product = fields.StringField()  # Crashed application name
    version = fields.StringField()  # Crashed application version
    platform = fields.StringField()  # OS name
    filename = fields.StringField()
    minidump = fields.FileField()  # Google Breakpad minidump
    stacktrace = fields.StringField()
    date_created = fields.DateTimeField(default=datetime.now())
    crash_reason = fields.StringField()

    def save_minidump(self, request):
        if not os.path.isdir(DUMPS_DIR):
            os.makedirs(DUMPS_DIR)
        try:
            file = request.files['upload_file_minidump']
            self.filename = secure_filename(file.filename)
            target_path = self.get_minidump_path()
            file.save(target_path)
            with open(target_path, 'rb') as minidump:
                if self.minidump:
                    self.minidump.replace(minidump)
                else:
                    self.minidump.put(minidump)
            self.save()
        except (KeyError, AttributeError) as e:
            raise e

    def get_minidump_path(self):
        return os.path.join(DUMPS_DIR, self.filename)

    def create_stacktrace(self):
        from oopsypad.server import worker
        worker.process_minidump.delay(str(self.id))

    def get_time(self):
        return self.date_created.strftime('%d.%m.%y %H:%M')

    @classmethod
    def create_minidump(cls, request):
        data = request.form
        minidump = cls(product=data['product'],
                       version=data['version'],
                       platform=data['platform'])

        cls.save_minidump(minidump, request)
        cls.create_stacktrace(minidump)
        return minidump

    @classmethod
    def get_last_12_months_minidumps_count(cls, queryset):
        today = datetime.now()
        counts = []
        for months in last_12_months():
            months_ago = today - relativedelta(months=months)
            one_less_months_ago = today - relativedelta(months=months + 1)
            months_ago_minidumps_count = queryset.filter(
                Q(date_created__lte=months_ago) & Q(date_created__gte=one_less_months_ago)).count()
            counts.append(months_ago_minidumps_count)
        return counts

    @classmethod
    def get_versions_per_product(cls, product):
        return sorted(list(set([i.version for i in cls.objects(product=product)])))

    def __str__(self):
        return "<Minidump: {} {} {} {}>".format(self.product,
                                                self.version,
                                                self.platform,
                                                self.filename)


class SymFile(mongo.Document):
    product = fields.StringField()
    version = fields.StringField()
    platform = fields.StringField()
    symfile_name = fields.StringField()
    symfile_id = fields.StringField()
    symfile = fields.FileField()

    def save_symfile(self, request):
        try:
            file = request.files['symfile']
            self.symfile_name = secure_filename(file.filename)
            target_path = self.get_symfile_path()
            if not os.path.isdir(target_path):
                os.makedirs(target_path)
            file.save(os.path.join(target_path, self.symfile_name))
            self.save()
        except(KeyError, AttributeError) as e:
            raise e

    def get_symfile_path(self):
        return os.path.join(SYMFILES_DIR, self.product, self.symfile_id)

    @classmethod
    def create_symfile(cls, request, product, id):
        data = request.form
        symfile = cls(product=product,
                      symfile_id=id,
                      version=data['version'],
                      platform=data['platform'])
        cls.save_symfile(symfile, request)
        return symfile

    def __str__(self):
        return "<SymFile: {} {} {} {}>".format(self.product,
                                               self.version,
                                               self.platform,
                                               self.symfile_id)


class Project(mongo.Document):
    name = fields.StringField(required=True, unique=True)
    min_version = fields.StringField()
    allowed_platforms = fields.ListField(fields.ReferenceField('Platform'))

    def get_allowed_platforms(self):
        return [i.name for i in self.allowed_platforms]

    def __str__(self):
        return "<Project: {} {} {}>".format(self.name,
                                            self.min_version,
                                            self.allowed_platforms)


class Platform(mongo.Document):
    platforms = ['Linux', 'MacOS', 'Windows']
    name = fields.StringField(required=True, unique=True, choices=platforms)

    def __str__(self):
        return self.name