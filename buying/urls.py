from django.urls import path
from . import views
urlpatterns = [
    path("purrequests/", views.CreatePurchaseRequest.as_view(), name="purchase_requests"),
    path("admin/requests/", views.AdminListRequests.as_view(), name="admin_list_requests"),
    path("admin/requests/<int:request_id>/process/", views.AdminProcessRequest.as_view(), name="admin_process_request"),
    path("userlibrary/", views.MyLibrary.as_view(), name="user_library"),
]
