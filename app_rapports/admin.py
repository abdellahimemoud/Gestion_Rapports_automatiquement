from django.contrib import admin
from .models import (
    DatabaseConnection,
    SqlQuery,
    Report,
    ReportExecutionLog,
)

# ==============================
# DATABASE CONNECTION
# ==============================
@admin.register(DatabaseConnection)
class DatabaseConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "host", "database_name", "port")
    search_fields = ("name", "host", "database_name")
    list_filter = ("host",)


# ==============================
# SQL QUERY
# ==============================
@admin.register(SqlQuery)
class SqlQueryAdmin(admin.ModelAdmin):
    list_display = ("name", "database", "created_at")
    search_fields = ("name", "sql_text")
    list_filter = ("database",)
    date_hierarchy = "created_at"


# ==============================
# INLINE LOGS (dans le rapport)
# ==============================
class ReportExecutionLogInline(admin.TabularInline):
    model = ReportExecutionLog
    extra = 0
    can_delete = False
    readonly_fields = ("query", "status", "message", "created_at")
    ordering = ("-created_at",)


# ==============================
# REPORT
# ==============================
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "subject",
        "is_periodic",
        "execute_at",
        "last_executed_at",
        "created_at",
    )

    list_filter = (
        "is_periodic",
        "periodic_type",
        "created_at",
    )

    search_fields = ("name", "subject", "message")

    filter_horizontal = (
        "queries",  # garder uniquement les relations existantes
    )

    readonly_fields = (
        "created_at",
        "last_executed_at",
    )

    inlines = [ReportExecutionLogInline]


# ==============================
# REPORT EXECUTION LOG (vue globale)
# ==============================
@admin.register(ReportExecutionLog)
class ReportExecutionLogAdmin(admin.ModelAdmin):
    list_display = (
        "report",
        "query",
        "status",
        "created_at",
        "short_message",
    )

    list_filter = (
        "status",
        "report",
        "created_at",
    )

    search_fields = (
        "message",
        "report__name",
        "query__name",
    )

    readonly_fields = (
        "report",
        "query",
        "status",
        "message",
        "created_at",
    )

    date_hierarchy = "created_at"

    def short_message(self, obj):
        return obj.message[:80] + ("..." if len(obj.message) > 80 else "")
    short_message.short_description = "Message"
