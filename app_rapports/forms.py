from django import forms
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


from .models import (
    DatabaseConnection,
    SqlQuery,
    Report,
)

# ============================================================
# FORMULAIRE CONNEXION BASE DE DONNÉES
# ============================================================

class DatabaseForm(forms.ModelForm):
    class Meta:
        model = DatabaseConnection
        fields = "__all__"
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "db_type": forms.Select(attrs={"class": "form-select"}),
            "host": forms.TextInput(attrs={"class": "form-control"}),
            "port": forms.NumberInput(attrs={"class": "form-control"}),
            "user": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}, render_value=True),
            "database_name": forms.TextInput(attrs={"class": "form-control"}),
        }


class DatabaseConnectionForm(forms.ModelForm):
    class Meta:
        model = DatabaseConnection
        fields = [
            "name", "db_type", "host",
            "port", "user", "password",
            "database_name",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "db_type": forms.Select(attrs={"class": "form-select"}),
            "host": forms.TextInput(attrs={"class": "form-control"}),
            "port": forms.NumberInput(attrs={"class": "form-control"}),
            "user": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control", "id": "id_password"}),
            "database_name": forms.TextInput(attrs={"class": "form-control"}),
        }


# ============================================================
# FORMULAIRE REQUÊTE SQL
# ============================================================

class QueryForm(forms.ModelForm):
    # 🔢 Colonnes à sommer (input texte)
    total_columns = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex: montant"
            }
        )
    )

    class Meta:
        model = SqlQuery
        fields = [
            "name",
            "sql_text",
            "database",

            # ➕ TOTAUX
            "enable_totals",
            "total_columns",
            "total_label",
        ]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "sql_text": forms.Textarea(
                attrs={"class": "form-control", "rows": 6}
            ),
            "database": forms.Select(attrs={"class": "form-select"}),

            "enable_totals": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "total_label": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "TOTAL"
                }
            ),
        }

    # ===============================
    # 🔐 Nettoyage colonnes
    # ===============================
    def clean_total_columns(self):
        value = self.cleaned_data.get("total_columns")

        if not value:
            return []

        return [
            v.strip()
            for v in value.split(",")
            if v.strip()
        ]

class SqlQueryForm(forms.ModelForm):

    # 🔢 Colonnes à sommer (input texte)
    total_columns = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex: montant"
            }
        )
    )

    class Meta:
        model = SqlQuery
        fields = [
            "name",
            "sql_text",
            "database",

            # ➕ TOTAUX
            "enable_totals",
            "total_columns",
            "total_label",
        ]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "sql_text": forms.Textarea(
                attrs={"class": "form-control", "rows": 6}
            ),
            "database": forms.Select(attrs={"class": "form-select"}),

            "enable_totals": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "total_label": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "TOTAL"
                }
            ),
        }

    # ===============================
    # 🔐 Nettoyage colonnes
    # ===============================
    def clean_total_columns(self):
        value = self.cleaned_data.get("total_columns")

        if not value:
            return []

        return [
            v.strip()
            for v in value.split(",")
            if v.strip()
        ]


# ============================================================
# FORMULAIRE RAPPORT (EMAILS JSON)
# ============================================================

class ReportForm(forms.ModelForm):
    
    queries = forms.ModelMultipleChoiceField(
        queryset=SqlQuery.objects.all().order_by("name"),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 6}),
        required=True,
    )

    execute_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    periodic_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    periodic_weekday = forms.ChoiceField(
        required=False,
        choices=Report.WEEKDAY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    periodic_monthday = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 31}),
    )

    class Meta:
        model = Report
        fields = [
            "name", "subject", "message",
            "queries",
            "is_periodic", "execute_at",
            "periodic_type", "periodic_time",
            "periodic_weekday", "periodic_monthday",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_periodic": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "periodic_type": forms.Select(attrs={"class": "form-select"}),
        }

    # ===============================
    # VALIDATION PLANIFICATION
    # ===============================
    def clean(self):
        cleaned_data = super().clean()
        
        is_periodic = cleaned_data.get("is_periodic")
        execute_at = cleaned_data.get("execute_at")
        periodic_type = cleaned_data.get("periodic_type")
        periodic_time = cleaned_data.get("periodic_time")
        periodic_weekday = cleaned_data.get("periodic_weekday")
        periodic_monthday = cleaned_data.get("periodic_monthday")  


        # VALIDATION EMAIL OBLIGATOIRE
        request = self.initial.get("request")

        to_emails = []
        cc_emails = []

        if request:
            to_emails = request.POST.getlist("to_emails[]")
            cc_emails = request.POST.getlist("cc_emails[]")
        
        is_create = self.instance.pk is None

        if is_create and not to_emails and not cc_emails:
            # Erreur globale comme un champ obligatoire
            self.add_error(None, "Vous devez ajouter au moins un mail")

       
        now = timezone.now()

        if is_periodic:
            if execute_at:
                self.add_error("execute_at", "Un rapport périodique ne doit pas avoir de date unique.")
            if not periodic_type:
                self.add_error("periodic_type", "Veuillez choisir un type de périodicité.")
            if not periodic_time:
                self.add_error("periodic_time", "Veuillez définir une heure d’exécution.")
            if periodic_type == "weekly" and not periodic_weekday:
                self.add_error("periodic_weekday", "Veuillez sélectionner un jour de la semaine.")
            if periodic_type == "monthly":
                if periodic_monthday is None:
                    self.add_error("periodic_monthday", "Veuillez définir le jour du mois.")
                elif not 1 <= periodic_monthday <= 31:
                    self.add_error("periodic_monthday", "Le jour du mois doit être entre 1 et 31.")
        else:
            if not execute_at:
                self.add_error("execute_at", "La date et l’heure d’exécution sont obligatoires.")
            elif execute_at <= now:
                self.add_error("execute_at", "La date et l’heure doivent être dans le futur.")
