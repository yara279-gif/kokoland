from django.db import models
from book.models import Customizations, Book
from user.models import User
# Create your models here.

class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    book = models.ForeignKey(Book, on_delete=models.CASCADE, blank=True, null=True)
    customization = models.ForeignKey(Customizations, on_delete=models.CASCADE,blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request {self.id} - {self.user.email} - {self.status}"
    

class UserLibrary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    custom_book = models.ForeignKey(Customizations, on_delete=models.CASCADE,blank=True, null=True)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} owns {self.custom_book}"
