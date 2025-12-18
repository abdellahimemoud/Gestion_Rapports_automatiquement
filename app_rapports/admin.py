from django.contrib import admin
from .models import DatabaseConnection, SqlQuery

admin.site.register(DatabaseConnection)
admin.site.register(SqlQuery)
