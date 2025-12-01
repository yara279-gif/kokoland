from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from book.models import Customizations

from .serializers import PurchaseRequestSerializer, AdminPurchaseUpdateSerializer, UserLibrarySerializer
from rest_framework.permissions import IsAdminUser
from .models import UserLibrary
from rest_framework import generics, permissions
from .models import PurchaseRequest, UserLibrary

class CreatePurchaseRequest(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        book_id = request.data.get("book_id")
        customization_id = request.data.get("customization_id")

        if not book_id and not customization_id:
            return Response({"error": "Either book_id or customization_id must be provided."}, status=400)

        purchase_request = PurchaseRequest.objects.create(
            user=user,
            book_id=book_id if book_id else None,
            customization_id=customization_id if customization_id else None,
        )
        return Response({"message": "Purchase request created.", "request_id": purchase_request.id}, status=201)
    
class AdminListRequests(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        requests = PurchaseRequest.objects.all()
        serializer = PurchaseRequestSerializer(requests, many=True)
        return Response(serializer.data)
    
class AdminProcessRequest(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, request_id):
        req = PurchaseRequest.objects.get(id=request_id)
        action = request.data.get("action")  # "approve" / "reject"

        if action == "approve":
            req.status = "approved"
            req.save()

            # Add book to user library
            UserLibrary.objects.create(
                user=req.user,
                custom_book=req.customization,
                book=req.book,
            )

            return Response({"msg": "Approved and added to user library"})

        elif action == "reject":
            req.status = "rejected"
            req.save()
            return Response({"msg": "Request rejected"})

        else:
            return Response({"error": "Invalid action"}, status=400)

#====================================================================================
class MyLibrary(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = UserLibrary.objects.filter(user=request.user)
        serializer = UserLibrarySerializer(items, many=True)
        return Response(serializer.data)
