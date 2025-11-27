from django.db import models
from django.utils import timezone
from user.models import User


# Create your models here.

class Book(models.Model):
    title = models.CharField(max_length=200)
    char_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    category = models.CharField(max_length=100)
    age= models.CharField(max_length=50)
    cover_image = models.ImageField(upload_to='media/covers/', null=True, blank=True)
    gender = models.CharField(max_length=50)
    rate = models.FloatField()
    description = models.TextField()
    published_date = models.DateTimeField(default=timezone.now)
    book_file = models.FileField(upload_to='media/books/')

    def __str__(self):
        return f"{self.title} to {self.char_name}"
    
class Customizations(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    child_name = models.CharField(max_length=100)
    child_image = models.ImageField(upload_to='media/child_images/')
    child_age = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    custom_book = models.FileField(upload_to='media/custom_books/')
    def __str__(self):
        return f"Customization for {self.child_name} in book {self.book.title}"
    