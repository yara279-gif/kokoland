from rest_framework import serializers
from .models import Book, Customizations
from django.urls import reverse

class BookSerializer(serializers.ModelSerializer):
    cover_image_url = serializers.SerializerMethodField()
    book_file_url = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id", "title", "char_name", "price", "category", 
            "age", "gender", "rate", "description", "published_date",
            "cover_image_url", "book_file_url",
        ]

    def get_cover_image_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.cover_image:
            return None
        return request.build_absolute_uri(
            reverse("book-cover", args=[obj.id])
        )

    def get_book_file_url(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        return request.build_absolute_uri(
            reverse("book-file", args=[obj.id])
        )

from rest_framework import serializers
from django.urls import reverse
from .models import Customizations

class CustomizationSerializer(serializers.ModelSerializer):
    child_image_url = serializers.SerializerMethodField()
    custom_book_url = serializers.SerializerMethodField()
    book_title = serializers.CharField(source='book.title', read_only=True)
    book_id = serializers.IntegerField(source='book.id', read_only=True)
    user_email = serializers.CharField(source='user_id.email', read_only=True)

    class Meta:
        model = Customizations
        fields = [
            "id",
            "book_id",
            "book_title",
            "user_id",
            "user_email",
            "child_name",
            "child_age",
            "created_at",
            "child_image_url",
            "custom_book_url",
        ]
        read_only_fields = ["id", "created_at"]

    def get_child_image_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.child_image:
            return None
        try:
            return request.build_absolute_uri(
                reverse("custom-child-image", args=[obj.id])
            )
        except Exception:
            return None

    def get_custom_book_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.custom_book:
            return None
        try:
            return request.build_absolute_uri(
                reverse("custom-book-file", args=[obj.id])
            )
        except Exception:
            return None