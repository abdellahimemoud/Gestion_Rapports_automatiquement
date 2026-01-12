from django.urls import path
from . import views

urlpatterns = [

    # ================= HOME =================
    path("", views.home, name="home"),

    # ================= DATABASES =================
    path("databases/", views.db_list, name="db_list"),
    path("databases/create/", views.db_create, name="db_create"),
    path("databases/test/<int:db_id>/", views.test_db_connection, name="db_test"),
    path("databases/update/<int:pk>/", views.db_update, name="db_update"),
    path("databases/delete/<int:pk>/", views.db_delete, name="db_delete"),

    # ================= QUERIES =================
    path("queries/", views.query_list, name="query_list"),
    path("queries/create/", views.query_create, name="query_create"),
    path("queries/parameters/", views.query_parameters, name="query_parameters"),
    path("queries/update/<int:pk>/", views.query_update, name="query_update"),
    path("queries/delete/<int:pk>/", views.query_delete, name="query_delete"),


    # ================= REPORTS =================
    path("reports/", views.report_list, name="report_list"),
    path("reports/create/", views.report_create, name="report_create"),
    path("reports/<int:pk>/edit/", views.report_update, name="report_update"),
    path("reports/<int:pk>/delete/", views.report_delete, name="report_delete"),
    path("reports/download/<int:rid>/", views.report_download, name="report_download"),
    path("reports/execute/<int:rid>/", views.report_execute, name="report_execute"),
    path("reports/<int:rid>/logs/", views.report_logs, name="report_logs"),



    # =================  EMAIL =================
    path("emails/save/", views.save_email, name="save_email"),
    

]
