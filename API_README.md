# Kokoland API Documentation

This document provides detailed information about the Kokoland API endpoints, including request and response examples.

## Base URL
The base URL for all endpoints is `{{base_url}}`. Replace this with your actual API base URL (e.g., `http://localhost:8000`).

## Authentication
Most endpoints require authentication using JWT tokens. Include the `Authorization` header with `Bearer {{access_token}}` for user endpoints or `Bearer {{admin_access_token}}` for admin-only endpoints.

## Home

### GET / - Home
Returns a welcome message indicating the API is working.

**Request:**
```
GET {{base_url}}/
```

**Success Response (200 OK):**
```json
{
    "message": "Kokoland API is working!"
}
```

## User Management

### POST /user/register/ - Register User
Register a new user account.

**Request:**
```
POST {{base_url}}/user/register/
Content-Type: application/json

{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "address": "123 Main St",
    "payment_info": "card_123456",
    "password": "password123",
    "password2": "password123"
}
```

**Success Response (201 Created):**
```json
{
    "token": {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    },
    "msg": "register successfull"
}
```

**Validation Error (400 Bad Request):**
```json
{
    "password2": [
        "password dont match"
    ]
}
```

### POST /user/login/ - Login User
Authenticate a user and return tokens.

**Request:**
```
POST {{base_url}}/user/login/
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "password123"
}
```

**Success Response (200 OK):**
```json
{
    "is_admin": false,
    "token": {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    },
    "msg": "login successfull"
}
```

**Invalid Credentials (401 Unauthorized):**
```json
{
    "msg": "invalid username or password"
}
```

### GET /user/profile/ - Get User Profile
Retrieve the authenticated user's profile information.

**Request:**
```
GET {{base_url}}/user/profile/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "id": 1,
    "email": "user@example.com",
    "is_admin": false,
    "first_name": "John",
    "last_name": "Doe",
    "image": null,
    "address": "123 Main St",
    "payment_info": "card_123456"
}
```

### PATCH /user/changepassword/ - Change Password
Change the authenticated user's password.

**Request:**
```
PATCH {{base_url}}/user/changepassword/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "old_password": "oldpassword123",
    "new_password": "newpassword123",
    "confirm_password": "newpassword123"
}
```

**Success Response (200 OK):**
```json
{
    "msg": "Password changed successfully"
}
```

**Validation Error (400 Bad Request):**
```json
{
    "old_password": [
        "Old password is incorrect."
    ]
}
```

### POST /user/addadmin/ - Add Admin (Admin Only)
Create a new admin user. Requires admin authentication.

**Request:**
```
POST {{base_url}}/user/addadmin/
Authorization: Bearer {{admin_access_token}}
Content-Type: application/json

{
    "first_name": "Admin",
    "last_name": "User",
    "email": "admin@example.com",
    "address": "456 Admin St",
    "payment_info": "admin_card",
    "password": "adminpass123"
}
```

**Success Response (201 Created):**
```json
{
    "id": 2,
    "first_name": "Admin",
    "last_name": "User",
    "is_admin": true,
    "email": "admin@example.com",
    "address": "456 Admin St",
    "payment_info": "admin_card"
}
```

**Access Denied (403 Forbidden):**
```json
{
    "message": "Don't have access"
}
```

### POST /user/adduser/ - Add User (Admin Only)
Create a new regular user. Requires admin authentication.

**Request:**
```
POST {{base_url}}/user/adduser/
Authorization: Bearer {{admin_access_token}}
Content-Type: application/json

{
    "first_name": "New",
    "last_name": "User",
    "email": "newuser@example.com",
    "password": "newuserpass123"
}
```

**Success Response (201 Created):**
```json
{
    "id": 3,
    "first_name": "New",
    "last_name": "User",
    "is_admin": false,
    "email": "newuser@example.com"
}
```

### GET /user/retrieveuser/{id}/ - Retrieve User (Admin Only)
Retrieve a specific user's information by ID. Requires admin authentication.

**Request:**
```
GET {{base_url}}/user/retrieveuser/1/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
{
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "is_admin": false,
    "email": "user@example.com",
    "password": "pbkdf2_sha256$..."
}
```

**User Not Found (200 OK):**
```json
{
    "message": "user not found"
}
```

### GET /user/searchuser/{first_name}/ - Search User (Admin Only)
Search for users by first name. Requires admin authentication.

**Request:**
```
GET {{base_url}}/user/searchuser/John/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "first_name": "John",
        "last_name": "Doe",
        "is_admin": false,
        "email": "user@example.com",
        "password": "pbkdf2_sha256$..."
    }
]
```

**User Not Found (200 OK):**
```json
{
    "message": "user not found"
}
```

### DELETE /user/deleteuser/{id}/ - Delete User (Admin Only)
Delete a user by ID. Requires admin authentication.

**Request:**
```
DELETE {{base_url}}/user/deleteuser/3/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
{
    "message": "deleted succesfully"
}
```

**User Not Found (200 OK):**
```json
{
    "message": "user not found"
}
```

### PATCH /user/updateuser/{id}/ - Update User (Admin Only)
Update a user's information by ID. Requires admin authentication.

**Request:**
```
PATCH {{base_url}}/user/updateuser/1/
Authorization: Bearer {{admin_access_token}}
Content-Type: application/json

{
    "first_name": "Updated",
    "last_name": "Name"
}
```

**Success Response (200 OK):**
```json
{
    "message": "updated succesfully"
}
```

### GET /user/listusers/ - List Users (Admin Only)
List all regular users. Requires admin authentication.

**Request:**
```
GET {{base_url}}/user/listusers/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "image": null,
        "is_admin": false
    }
]
```

### GET /user/listadmins/ - List Admins (Admin Only)
List all admin users. Requires admin authentication.

**Request:**
```
GET {{base_url}}/user/listadmins/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 2,
        "email": "admin@example.com",
        "first_name": "Admin",
        "last_name": "User",
        "image": null,
        "is_admin": true
    }
]
```

### POST /user/logout/ - Logout User
Logout the authenticated user by blacklisting the refresh token.

**Request:**
```
POST {{base_url}}/user/logout/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Success Response (200 OK):**
```json
{
    "msg": "Logged out successfully"
}
```

**Invalid Token (400 Bad Request):**
```json
{
    "msg": "Invalid token"
}
```

### DELETE /user/deleteaccount/ - Delete Account
Delete the authenticated user's account.

**Request:**
```
DELETE {{base_url}}/user/deleteaccount/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "msg": "Account deleted successfully"
}
```

### GET /user/updateprofile/ - Get Profile for Update
Get the authenticated user's profile data for updating.

**Request:**
```
GET {{base_url}}/user/updateprofile/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "image": null,
    "address": "123 Main St",
    "payment_info": "card_123456"
}
```

### PUT /user/updateprofile/ - Update Profile
Update the authenticated user's profile information.

**Request:**
```
PUT {{base_url}}/user/updateprofile/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "email": "updated@example.com",
    "first_name": "Updated",
    "last_name": "Name",
    "address": "456 Updated St",
    "payment_info": "updated_card"
}
```

**Success Response (200 OK):**
```json
{
    "msg": [
        "first_name updated successfully",
        "last_name updated successfully",
        "address updated successfully",
        "payment_info updated successfully"
    ]
}
```

**No Changes (406 Not Acceptable):**
```json
{
    "msg": "No changes made"
}
```

### PATCH /user/updateprofile/ - Partial Update Profile
Partially update the authenticated user's profile.

**Request:**
```
PATCH {{base_url}}/user/updateprofile/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "first_name": "Patched"
}
```

**Success Response (200 OK):**
```json
{
    "msg": "Profile updated successfully"
}
```

### POST /user/sendrestpasswordemail/ - Send Reset Password Email
Send a password reset email to the specified email address.

**Request:**
```
POST {{base_url}}/user/sendrestpasswordemail/
Content-Type: application/json

{
    "email": "user@example.com"
}
```

**Success Response (200 OK):**
```json
{
    "msg": "password resert link was send .please check your email"
}
```

**User Not Found (400 Bad Request):**
```json
{
    "email": [
        "User not found"
    ]
}
```

### POST /user/resetpassword/{uid}/{token}/ - Reset Password
Reset the user's password using the reset token.

**Request:**
```
POST {{base_url}}/user/resetpassword/MQ/abc123def456/
Content-Type: application/json

{
    "password": "newpassword123",
    "confirm_password": "newpassword123"
}
```

**Success Response (200 OK):**
```json
{
    "success_message": "Password has been reset successfully. go to login page"
}
```

**Expired Link (408 Request Timeout):**
```json
{
    "error_message": "Expired link of Rest Password \n please go to forget password page."
}
```

### POST /user/createadmin/ - Create Admin
Create the first admin user (used for initial setup).

**Request:**
```
POST {{base_url}}/user/createadmin/
Content-Type: application/json

{
    "email": "superadmin@example.com",
    "first_name": "Super",
    "last_name": "Admin",
    "password": "superadmin123",
    "password2": "superadmin123"
}
```

**Success Response (201 Created):**
```json
{
    "email": "superadmin@example.com",
    "first_name": "Super",
    "last_name": "Admin",
    "image": null,
    "is_superuser": true,
    "is_staff": true,
    "is_admin": true
}
```

## Book Management

### POST /books/customize/ - Customize Book
Customize a book by replacing the main character with a child's name and image.

**Request:**
```
POST {{base_url}}/books/customize/
Authorization: Bearer {{access_token}}
Content-Type: multipart/form-data

book: 1
child_name: Alice
child_age: 5
child_image: [file]
```

**Success Response (201 Created):**
```json
{
    "success": true,
    "message": "Book customized successfully!",
    "customization_id": 1,
    "book_id": 1,
    "book_title": "Sample Book",
    "child_name": "Alice",
    "images_processed": 5,
    "total_images": 5,
    "character_replacements": 3,
    "character_replaced": true,
    "original_character_name": "Tommy",
    "custom_book_url": "http://localhost:8000/books/customizations/1/file/",
    "child_image_url": "http://localhost:8000/books/customizations/1/child-image/",
    "ai_processing_used": true,
    "created_at": "2024-01-15T10:30:00Z"
}
```

**Validation Error (400 Bad Request):**
```json
{
    "error": "book_id, child_name and child_image are required."
}
```

### GET /books/listcustomizations/ - List Customizations
List all customizations for the authenticated user.

**Request:**
```
GET {{base_url}}/books/listcustomizations/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "success": true,
    "count": 1,
    "customizations": [
        {
            "id": 1,
            "book": {
                "id": 1,
                "title": "Sample Book",
                "char_name": "Tommy",
                "price": 10.99,
                "category": "Adventure",
                "age": "5-7",
                "gender": "unisex",
                "rate": 4.5,
                "description": "A fun adventure book",
                "book_file": "http://localhost:8000/books/bookfile/1/",
                "cover_image": "http://localhost:8000/books/cover/1/",
                "book_file_type": "application/pdf",
                "cover_image_type": "image/jpeg"
            },
            "child_name": "Alice",
            "child_age": "5",
            "custom_book": "<binary_data>",
            "custom_book_type": "application/pdf",
            "child_image": "<binary_data>",
            "child_image_type": "image/jpeg",
            "user": 1,
            "created_at": "2024-01-15T10:30:00Z"
        }
    ]
}
```

### GET /books/customizations/{pk}/ - Get Customization
Retrieve a specific customization by ID.

**Request:**
```
GET {{base_url}}/books/customizations/1/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "success": true,
    "customization": {
        "id": 1,
        "book": {
            "id": 1,
            "title": "Sample Book",
            "char_name": "Tommy",
            "price": 10.99,
            "category": "Adventure",
            "age": "5-7",
            "gender": "unisex",
            "rate": 4.5,
            "description": "A fun adventure book",
            "book_file": "http://localhost:8000/books/bookfile/1/",
            "cover_image": "http://localhost:8000/books/cover/1/",
            "book_file_type": "application/pdf",
            "cover_image_type": "image/jpeg"
        },
        "child_name": "Alice",
        "child_age": "5",
        "custom_book": "<binary_data>",
        "custom_book_type": "application/pdf",
        "child_image": "<binary_data>",
        "child_image_type": "image/jpeg",
        "user": 1,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

### DELETE /books/customizations/{pk}/delete/ - Delete Customization
Delete a customization by ID.

**Request:**
```
DELETE {{base_url}}/books/customizations/1/delete/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "success": true,
    "message": "Customization for 'Alice' of 'Sample Book' deleted successfully"
}
```

### GET /books/customizations/{pk}/file/ - Get Custom Book File
Download the customized book PDF file.

**Request:**
```
GET {{base_url}}/books/customizations/1/file/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="Alice_Sample_Book.pdf"

<PDF_BINARY_DATA>
```

### GET /books/customizations/{pk}/child-image/ - Get Child Image
Download the child's image used in customization.

**Request:**
```
GET {{base_url}}/books/customizations/1/child-image/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```
Content-Type: image/jpeg
Content-Disposition: inline; filename="Alice_photo.jpg"

<IMAGE_BINARY_DATA>
```

### GET /books/bookfile/{pk}/ - Get Book File
Download the original book PDF file.

**Request:**
```
GET {{base_url}}/books/bookfile/1/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```
Content-Type: application/pdf
Content-Disposition: inline; filename="Sample_Book.pdf"

<PDF_BINARY_DATA>
```

### GET /books/cover/{pk}/ - Get Book Cover
Download the book cover image.

**Request:**
```
GET {{base_url}}/books/cover/1/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```
Content-Type: image/jpeg
Content-Disposition: inline; filename="Sample_Book_cover.jpg"

<IMAGE_BINARY_DATA>
```

### POST /books/addbook/ - Add Book
Add a new book to the catalog.

**Request:**
```
POST {{base_url}}/books/addbook/
Authorization: Bearer {{access_token}}
Content-Type: multipart/form-data

title: New Book Title
char_name: Character Name
price: 15.99
category: Fiction
age: 6-8
gender: unisex
rate: 4.8
description: A wonderful new book
book_file: [file]
cover_image: [file]
```

**Success Response (201 Created):**
```json
{
    "msg": "Book added successfully",
    "data": {
        "id": 2,
        "title": "New Book Title",
        "char_name": "Character Name",
        "price": 15.99,
        "category": "Fiction",
        "age": "6-8",
        "gender": "unisex",
        "rate": 4.8,
        "description": "A wonderful new book",
        "book_file": "http://localhost:8000/books/bookfile/2/",
        "cover_image": "http://localhost:8000/books/cover/2/",
        "book_file_type": "application/pdf",
        "cover_image_type": "image/jpeg"
    },
    "book_file_url": "http://localhost:8000/books/bookfile/2/",
    "cover_image_url": "http://localhost:8000/books/cover/2/"
}
```

**Validation Error (400 Bad Request):**
```json
{
    "error": "Book PDF file is required"
}
```

### GET /books/books/ - List Books
List all available books.

**Request:**
```
GET {{base_url}}/books/books/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "title": "Sample Book",
        "char_name": "Tommy",
        "price": 10.99,
        "category": "Adventure",
        "age": "5-7",
        "gender": "unisex",
        "rate": 4.5,
        "description": "A fun adventure book",
        "book_file": "http://localhost:8000/books/bookfile/1/",
        "cover_image": "http://localhost:8000/books/cover/1/",
        "book_file_type": "application/pdf",
        "cover_image_type": "image/jpeg"
    }
]
```

### GET /books/books/{pk}/ - Retrieve One Book
Retrieve a specific book by ID.

**Request:**
```
GET {{base_url}}/books/books/1/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
{
    "id": 1,
    "title": "Sample Book",
    "char_name": "Tommy",
    "price": 10.99,
    "category": "Adventure",
    "age": "5-7",
    "gender": "unisex",
    "rate": 4.5,
    "description": "A fun adventure book",
    "book_file": "http://localhost:8000/books/bookfile/1/",
    "cover_image": "http://localhost:8000/books/cover/1/",
    "book_file_type": "application/pdf",
    "cover_image_type": "image/jpeg"
}
```

**Not Found (404 Not Found):**
```json
{
    "msg": "Not found"
}
```

### PATCH /books/update_book/{pk}/ - Update Book
Update a book's information by ID.

**Request:**
```
PATCH {{base_url}}/books/update_book/1/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "title": "Updated Book Title",
    "price": 12.99
}
```

**Success Response (200 OK):**
```json
{
    "msg": "Book updated successfully",
    "data": {
        "id": 1,
        "title": "Updated Book Title",
        "char_name": "Tommy",
        "price": 12.99,
        "category": "Adventure",
        "age": "5-7",
        "gender": "unisex",
        "rate": 4.5,
        "description": "A fun adventure book",
        "book_file": "http://localhost:8000/books/bookfile/1/",
        "cover_image": "http://localhost:8000/books/cover/1/",
        "book_file_type": "application/pdf",
        "cover_image_type": "image/jpeg"
    }
}
```

### DELETE /books/delete_book/{pk}/ - Delete Book
Delete a book by ID.

**Request:**
```
DELETE {{base_url}}/books/delete_book/1/
Authorization: Bearer {{access_token}}
```

**Success Response (204 No Content):**
```json
{
    "msg": "Deleted successfully"
}
```

**Not Found (404 Not Found):**
```json
{
    "error": "Book not found"
}
```

### POST /books/search_books/ - Search Books
Search for books based on criteria.

**Request:**
```
POST {{base_url}}/books/search_books/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "title": "Adventure",
    "category": "Fiction",
    "age": "5-7"
}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "title": "Sample Book",
        "char_name": "Tommy",
        "price": 10.99,
        "category": "Adventure",
        "age": "5-7",
        "gender": "unisex",
        "rate": 4.5,
        "description": "A fun adventure book",
        "book_file": "http://localhost:8000/books/bookfile/1/",
        "cover_image": "http://localhost:8000/books/cover/1/",
        "book_file_type": "application/pdf",
        "cover_image_type": "image/jpeg"
    }
]
```

**No Books Found (404 Not Found):**
```json
{
    "msg": "No books found"
}
```

## Buying Management

### POST /buy/purrequests/ - Create Purchase Request
Create a purchase request for a book.

**Request:**
```
POST {{base_url}}/buy/purrequests/
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
    "book_id": 1
}
```

**Success Response (201 Created):**
```json
{
    "message": "Purchase request created.",
    "request_id": 1
}
```

**Access Denied (403 Forbidden):**
```json
{
    "error": "Admins cannot create purchase requests."
}
```

### GET /buy/admin/requests/ - Admin List Requests
List all purchase requests for admin processing.

**Request:**
```
GET {{base_url}}/buy/admin/requests/
Authorization: Bearer {{admin_access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "user": 1,
        "book": 1,
        "customization": null,
        "status": "pending",
        "created_at": "2024-01-15T10:30:00Z"
    }
]
```

### POST /buy/admin/requests/{request_id}/process/ - Admin Process Request
Approve or reject a purchase request.

**Request:**
```
POST {{base_url}}/buy/admin/requests/1/process/
Authorization: Bearer {{admin_access_token}}
Content-Type: application/json

{
    "action": "approve"
}
```

**Approve Success (200 OK):**
```json
{
    "msg": "Approved and added to user library"
}
```

**Reject Success (200 OK):**
```json
{
    "msg": "Request rejected"
}
```

**Invalid Action (400 Bad Request):**
```json
{
    "error": "Invalid action"
}
```

### GET /buy/userlibrary/ - My Library
Get the authenticated user's purchased books library.

**Request:**
```
GET {{base_url}}/buy/userlibrary/
Authorization: Bearer {{access_token}}
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "user": 1,
        "book": {
            "id": 1,
            "title": "Sample Book",
            "char_name": "Tommy",
            "price": 10.99,
            "category": "Adventure",
            "age": "5-7",
            "gender": "unisex",
            "rate": 4.5,
            "description": "A fun adventure book",
            "book_file": "http://localhost:8000/books/bookfile/1/",
            "cover_image": "http://localhost:8000/books/cover/1/",
            "book_file_type": "application/pdf",
            "cover_image_type": "image/jpeg"
        },
        "custom_book": null,
        "added_at": "2024-01-15T10:30:00Z"
    }
]
```

**Access Denied (403 Forbidden):**
```json
{
    "error": "Admins/staff cannot access this endpoint."
}
