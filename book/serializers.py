from rest_framework import serializers
from .models import Book, Customizations

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'
        extra_kwargs = {
            "cover_image": {"required": False}
        }

class CustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customizations
        fields = [
            "id", "book", "user_id", "child_name",
            "child_image", "child_age", "created_at", "custom_book"
        ]
        read_only_fields = ["id", "created_at", "custom_book"]




class search_book(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            "title",
            "category"
            
        ]
