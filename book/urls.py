from django.urls import path, include
from . import views
urlpatterns = [
    path('customize/', views.CustomizeBook.as_view(), name='customize_book'),
]
