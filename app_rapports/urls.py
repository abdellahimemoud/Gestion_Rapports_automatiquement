from django.urls import path
from . import views

urlpatterns = [

    # ================= HOME =================
    path("", views.home, name="home"),

    # ================= DATABASES =================
    path("databases/", views.db_list, name="db_list"),
    path("databases/create/", views.db_create, name="db_create"),
    path("databases/test/<int:db_id>/", views.test_db_connection, name="db_test"),

    # ================= QUERIES =================
    path("queries/", views.query_list, name="query_list"),
    path("queries/create/", views.query_create, name="query_create"),


    # ================= REPORTS =================
    path("reports/", views.report_list, name="report_list"),
    path("reports/create/", views.report_create, name="report_create"),
    path("reports/<int:rid>/", views.report_detail, name="report_detail"),
    path("reports/download/<int:rid>/", views.report_download, name="report_download"),
    path("reports/execute/<int:rid>/", views.report_execute, name="report_execute"),
    path("reports/<int:rid>/logs/", views.report_logs, name="report_logs"),
    

]
