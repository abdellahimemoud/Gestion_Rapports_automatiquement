from django.urls import path
from . import views

urlpatterns = [
    # Page d'accueil
    path('', views.home, name='home'),

    # Bases de données
    path('dbs/', views.db_list, name='db_list'),
    path('dbs/create/', views.db_create, name='db_create'),
    path("db/test/<int:db_id>/", views.test_db_connection, name="test_db_connection"),

    # Requêtes SQL
    path('queries/', views.query_list, name='query_list'),
    path('queries/create/', views.query_create, name='query_create'),
    path('queries/run/<int:qid>/', views.query_run, name='query_run'),
    path('download/<int:qid>/', views.query_download, name='query_download'),

    # Emails
    path("save-email/", views.save_email, name="save_email"),
]
