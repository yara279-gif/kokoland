from django.urls import path, include
from . import views
urlpatterns = [
    path('customize/', views.CustomizeBook.as_view(), name='customize_book'),
    path('listcustomizations/', views.listCustomizedBooks, name='list_customizations'),
    path('addbook/', views.addbook, name='add_book'),
    path('books/', views.list_books, name='list_books'),
    path('books/<int:pk>/', views.retrieve_one_book, name='retrieve_one_book'),
    path('update_book/<int:pk>/', views.update_book, name='update_book'),
    path('delete_book/<int:pk>/', views.delete_book, name='delete_book'),
    path('search_books/', views.search_about_book, name='search_books'),
]
