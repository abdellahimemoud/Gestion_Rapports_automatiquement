import os
from celery import Celery

# =========================
# DJANGO SETTINGS
# =========================
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'rapports.settings'
)

# =========================
# CREATE CELERY APP
# =========================
app = Celery('rapports')

# =========================
# LOAD CONFIG FROM DJANGO
# =========================
# Toutes les variables commencent par CELERY_
app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

# =========================
# AUTO DISCOVER TASKS
# =========================
# Cherche tasks.py dans toutes les apps installées
app.autodiscover_tasks()


# =========================
# DEBUG (OPTIONNEL MAIS UTILE)
# =========================
@app.task(bind=True)
def debug_task(self):
    print(f"[CELERY DEBUG] Request: {self.request!r}")
