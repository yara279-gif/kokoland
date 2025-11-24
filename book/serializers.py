from rest_framework import serializers
from .models import Book, Customizations

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'

class CustomizationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customizations
        fields = '__all__'