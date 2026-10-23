from django.contrib import admin

from django.contrib import admin
from .models import Student, Subject, workType, Coefficient, Grade

admin.site.register([Student, Subject, workType, Coefficient, Grade])
