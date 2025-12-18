from rest_framework import serializers
from .models import DatabaseConnection, SqlQuery

class DatabaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatabaseConnection
        fields = '__all__'

class QuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SqlQuery
        fields = '__all__'
