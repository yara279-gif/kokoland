from django.urls import path, include
from . import views
urlpatterns = [
    # Customization endpoints
    path('customize/', views.CustomizeBook.as_view(), name='customize-book'),
    path('listcustomizations/', views.listCustomizedBooks, name='list-customizations'),
    path('customizations/<int:pk>/', views.getCustomization, name='get-customization'),
    path('customizations/<int:pk>/delete/', views.deleteCustomization, name='delete-customization'),
    path('customizations/<int:pk>/file/', views.CustomBookFileView.as_view(), name='custom-book-file'),
    path('customizations/<int:pk>/child-image/', views.CustomChildImageView.as_view(), name='custom-child-image'),
    path("bookfile/<int:pk>/", views.BookFileView.as_view(), name="book-file"),
    path('cover/<int:pk>/', views.BookCoverView.as_view(), name='book-cover'),
    path('addbook/', views.addbook, name='add_book'),
    path('books/', views.list_books, name='list_books'),
    path('books/<int:pk>/', views.retrieve_one_book, name='retrieve_one_book'),
    path('update_book/<int:pk>/', views.update_book, name='update_book'),
    path('delete_book/<int:pk>/', views.delete_book, name='delete_book'),
    path('search_books/', views.search_about_book, name='search_books'),
]
