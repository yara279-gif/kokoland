from rest_framework import serializers
from .models import PurchaseRequest, UserLibrary

class PurchaseRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseRequest
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'status']

class AdminPurchaseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseRequest
        fields = ['status']

class UserLibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLibrary
        fields = '__all__'
        read_only_fields = ['id', 'added_at']
        