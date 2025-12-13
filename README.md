# Kokoland

**Kokoland** is project to bookstore and you can customize your book and put your child name and face on the character of the book

---

## Table of Contents

- [Features](#features)   
- [Usage](#usage)    


---

## Features

- Feature 1: *admistration of users and books*  
- Feature 2: *buy and sale books*  
- Feature 3: *custoimze your book*  


---

## Usage 
each endpoint will be discriped
### Authentication

| Method     | Endpoint              | Description                            |
| ---------- | --------------------- | -------------------------------------- |
| **POST**   | `/user/register/`      | Register a new user                    |
| **POST**   | `/user/login/`         | Login and get JWT tokens               |
| **POST**   | `/user/logout/`        | Logout (blacklist refresh token)       |
| **DELETE** | `/user/deleteaccount/` | Delete currently authenticated account |
| **GET**    | `/user/profile/`       | Get authenticated user profile         |


### User Profile

| Method  | Endpoint              | Description                       |
| ------- | --------------------- | --------------------------------- |
| **PUT** | `/user/updateprofile/` | Update authenticated user profile |

### Password Management

| Method   | Endpoint                            | Description                      |
| -------- | ----------------------------------- | -------------------------------- |
| **POST** | `/user/changepassword/`              | Change password (old → new)      |
| **POST** | `/user/sendrestpasswordemail/`       | Send reset password email        |
| **POST** | `/user/resetpassword/<uid>/<token>/` | Reset password using email token |

### Admin User Management (Admin Only)

| Method    | Endpoint                   | Description             |
| --------- | -------------------------- | ----------------------- |
| **POST**  | `/user/addadmin/`           | Create a new admin user |
| **POST**  | `/user/adduser/`            | Create a regular user   |
| **GET**   | `/user/listusers/`          | List all users          |
| **GET**   | `/user/retrieveuser/<id>/`  | Get user details by ID  |
| **GET**   | `/user/searchuser/<email>/` | Search user by email    |
| **POST**  | `/user/deleteuser/<id>/`    | Delete a user           |
| **PATCH** | `/user/updateuser/<id>/`    | Update a user           |

##Input (Request Body)
### Register
request 
```json

{
    "email":"yaraharby1@gmail.com",
    "first_name":"yra",
    "last_name":"yaya",
    "address":"imbaba",
    "payment_info":"visa",
    "password":"123",
    "password2":"123"
}
```
Output (Response)
```json
{
    "is_admin": true,
    "token": {
        "refresh": "",
        "access": ""
    },
    "msg": "login successfull"
}
```

Login
Input
```json

{
  "email": "user@example.com",
  "password": "12345678"
}

Output
{
    "is_admin": true,
    "token": {
        "refresh": "",
        "access": ""
    },
    "msg": "login successfull"
}
```
User Profile
Serializer: userProfileSerializer
Output Example
```json

{
  "id": 1,
  "email": "user@example.com",
  "is_admin": false,
  "first_name": "Yara",
  "last_name": "Harby",
  "image": "http://127.0.0.1:8000/media/profile.jpg",
  "address": "Giza",
  "payment_info": "Visa 1234"
}
```
logout
```json
{
    "refresh_token":""
}
```

Update Profile

PUT /user/updateprofile/
Authorization: Bearer <access_token>

Input
```json
{
  "email": "user@example.com",
  "username": "yara279",
  "first_name": "Yara",
  "last_name": "Harby",
  "image": null,
  "address": "Giza",
  "payment_info": "Visa 1234"
}
```
Output
```json


{
  "email": "user@example.com",
  "username": "yara279",
  "first_name": "Yara",
  "last_name": "Harby",
  "image": null,
  "address": "Giza",
  "payment_info": "Visa 1234"
}
```
Change Password
input
```json
{
  "old_password": "oldpass123",
  "new_password": "newpass123",
  "confirm_password": "newpass123"
}
```
Output
```json


{
  "message": "Password updated successfully"
}
```
Send Reset Password Email
input
```json
{
  "email": "user@example.com"
}
Output
{
  "message": "Reset password link sent to your email"
}
```
Reset Password
input
```json
{
  "password": "newpass123",
  "confirm_password": "newpass123"
}
```
Output
```json
{
  "message": "Password reset successful"
}
```
Add Admin
Input
```json
{
  "first_name": "Admin",
  "last_name": "User",
  "email": "admin@example.com",
  "address": "Giza",
  "payment_info": "Bank 123",
  "password": "admin123"
}
```
Output
```json
{
  "id": 5,
  "first_name": "Admin",
  "last_name": "User",
  "is_admin": true,
  "email": "admin@example.com",
  "address": "Giza",
  "payment_info": "Bank 123"
}
```
Add User (Admin creates user)
Input
```json
{
  "first_name": "Sara",
  "last_name": "Mohamed",
  "email": "sara@example.com",
  "password": "sara123"
}
```
Output
```json
{
  "id": 12,
  "first_name": "Sara",
  "last_name": "Mohamed",
  "is_admin": false,
  "email": "sara@example.com"
}

```
List Users

```json
[
  {
    "id": 1,
    "username": "yara279",
    "first_name": "Yara",
    "last_name": "Harby",
    "image": null,
    "is_admin": false
  },
  {
    "id": 2,
    "username": "admin01",
    "first_name": "Admin",
    "last_name": "User",
    "image": "/media/profile.jpg",
    "is_admin": true
  }
]
```
retrieve user
GET /user/retrieveuser/<pk:id>/

Description: Get user details by ID

Request
`GET /user/retrieveuser/1/`

```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "Yara",
  "last_name": "Harby"
}

```
search user
GET /user/searchuser/<str:first_name>/

Description: Search user by first name

Request
`GET /user/searchuser/Yara/`
Response
```json
[
  {
    "email": "user@example.com",
    "first_name": "Yara"
  }
]

```
PATCH /user/updateuser/<pk:id>/

Description: Update user

Request
```json
{
  "first_name": "NewName"
}

```
Response
```json
{
  "message": "updated succesfully"
}

```
DELETE /user/deleteuser/<pk:id>/

Description: Delete a user

Request
`DELETE /user/deleteuser/1/`
Response
```json
{
  "message": "deleted succesfully"
}

```






### 📚 Personalized Children’s Book Customization API

A Django REST Framework project that customizes children’s books by replacing character faces and names inside a PDF.
The system extracts images from a PDF, applies AI face-swap, replaces character names using PDF.co API, and generates a personalized book for the child.

### 🚀 Features
### ✅ Book Management

Add books with: title, character name, description, price, age group, gender, category

Upload book cover & book PDF

### 🎨 Customization System

Upload child’s name + child’s photo

Extract all images from the PDF

Process each image using AI face-swap model

Replace book character’s name with the child’s name using PDF.co Text Replacement API

Generate a final personalized PDF

Save customization record in database

### 🧠 Technology Stack

Backend: Django, Django REST Framework

AI Model: FastAPI service (face-transfer) with InSwapper 128

PDF Processing: PyMuPDF (fitz)

Text Replacement: PDF.co API

Storage: Django FileField (local or cloud)

Image Processing: Pillow (PIL)

### 🗂 Models
Book
title, char_name, price, category, age, cover_image,
gender, rate, description, published_date, book_file

Customizations
book, user_id, child_name, child_image,
child_age, custom_book, created_at

### 🔌 API Endpoints
POST /customize-book/

Customize the children’s book.

| Field       | Type   | Required | Description      |
| ----------- | ------ | -------- | ---------------- |
| book        | int    | ✓        | Book ID          |
| user_id     | int    | ✓        | User ID          |
| child_name  | string | ✓        | Child's name     |
| child_image | file   | ✓        | Child’s photo    |
| child_age   | string | ✗        | For profile only |

## 📌 Book App Endpoints

Below is the list of API endpoints available in the Book application:

### 🔧 Customization


| Method   | Endpoint               | Description                                                      |
| -------- | ---------------------- | ---------------------------------------------------------------- |
| **POST** | `books/customize/`          | Customize an existing book (handled by `CustomizeBook` APIView). |
| **GET**  | `books/listcustomizations/` | List all customized books.                                       |

### 📚 Books CRUD

| Method     | Endpoint             | Description                    |
| ---------- | -------------------- | ------------------------------ |
| **POST**   | `books/addbook/`          | Add a new book.                |
| **GET**    | `books/books/`            | List all books.                |
| **GET**    | `books/books/<pk>/`       | Retrieve a single book by ID.  |
| **PUT**    | `books/update_book/<pk>/` | Update an existing book by ID. |
| **DELETE** | `books/delete_book/<pk>/` | Delete a book by ID.           |

### 🔍 Search
| Method  | Endpoint                          | Description                                     |
| ------- | --------------------------------- | ----------------------------------------------- |
| **GET** | `books/search_books/?q=<search_query>` | Search for books by title, author, or category. |
add book 
`books/addbook/`
Request
```json
{
  "title": "The AI Revolution",
  "author": "John Smith",
  "description": "A deep dive into AI concepts",
  "category": "Technology",
  "price": 120.5
}

```
Response
```json
{
  "message": "Book added successfully",
  "book": {
    "id": 1,
    "title": "The AI Revolution",
    "author": "John Smith",
    "description": "A deep dive into AI concepts",
    "category": "Technology",
    "price": 120.5
  }
}

```
List Books (books)
`books/books/`
Response
```json
[
  {
    "id": 1,
    "title": "The AI Revolution",
    "author": "John Smith",
    "category": "Technology",
    "price": 120.5
  },
  {
    "id": 2,
    "title": "Deep Learning Basics",
    "author": "Andrew Ng",
    "category": "AI",
    "price": 99.9
  }
]

```
Retrieve Book
`books/books/<pk>/`
Response
```json
{
  "id": 1,
  "title": "The AI Revolution",
  "author": "John Smith",
  "description": "A deep dive into AI concepts",
  "category": "Technology",
  "price": 120.5
}

```
Update Book
`books/update_book/<pk>/`
Request
```json
{
  "title": "The AI Revolution - Updated Edition",
  "price": 140.0
}

```
Response
```json
{
  "message": "Book updated successfully",
  "book": {
    "id": 1,
    "title": "The AI Revolution - Updated Edition",
    "author": "John Smith",
    "description": "A deep dive into AI concepts",
    "category": "Technology",
    "price": 140.0
  }
}

```
Delete Book
`books/delete_book/<pk>/`
Response
```json
{
  "message": "Book deleted successfully"
}

```
Search Books
 `books/search_books/?q=<search_query>`
Response
```json
[
  {
    "id": 1,
    "title": "The AI Revolution",
    "author": "John Smith",
    "category": "Technology"
  }
]
```
Customize Book
`books/customize/`  
Request
```json
{
  "book_id": 1,
  "cover_color": "blue",
  "font_size": 18,
  "note": "Gift edition"
}

```
Response
```json
{
  "message": "Book customized successfully",
  "customization": {
    "id": 3,
    "book_id": 1,
    "cover_color": "blue",
    "font_size": 18,
    "note": "Gift edition"
  }
}

```
List Customizations
`books/listcustomizations/`
Response
```json
[
  {
    "id": 3,
    "book": "The AI Revolution",
    "cover_color": "blue",
    "font_size": 18,
    "note": "Gift edition"
  }
]


```
## buying app

| Method   | Endpoint                                | Description                                                |
| -------- | --------------------------------------- | ---------------------------------------------------------- |
| **POST** | `buy/purrequests/`                         | Create a new purchase request (book or customization)      |
| **GET**  | `buy/admin/requests/`                      | Admin: List all purchase requests                          |
| **POST** | `buy/admin/requests/<request_id>/process/` | Admin: Approve or reject a purchase request                |
| **GET**  | `buy/userlibrary/`                         | Get all books/customizations in the current user’s library |
Create Purchase Request
`buy/purrequests/`  
```json
{
  "book_id": 1,
  "customization_id": null
}

```
Response
```json
{
  "message": "Purchase request created.",
  "request_id": 5
}

```
Admin List All Requests
 `buy/admin/requests/`   
Response
```json
[
  {
    "id": 5,
    "book": 1,
    "customization": null,
    "user": 2,
    "status": "pending",
    "created_at": "2025-12-03T14:35:12Z"
  },
  {
    "id": 6,
    "book": null,
    "customization": 3,
    "user": 4,
    "status": "approved",
    "created_at": "2025-12-01T10:22:45Z"
  }
]

```
Admin Process Request
`buy/admin/requests/<request_id>/process/`
```json
{
  "action": "approve"
}

```
Response – Approve
```json
{
  "msg": "Approved and added to user library"
}

```
Response – Reject
```json
{
  "msg": "Request rejected"
}

```
Get User Library (books)
`buy/userlibrary/`
Response
```json
[
  {
    "id": 1,
    "user": 2,
    "custom_book": 3,
    "book": null,
    "added_at": "2025-12-03T14:40:10Z"
  },
  {
    "id": 2,
    "user": 2,
    "custom_book": null,
    "book": 1,
    "added_at": "2025-11-29T09:10:50Z"
  }
]

```
