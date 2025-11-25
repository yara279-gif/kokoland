# Kokoland

**Kokoland** is project to bookstore and you can customize your book and put your child name and face on the character of the book

---

## Table of Contents

- [Features](#features)   
- [Usage](#usage)    


---

## Features

- Feature 1: *admistration of users and books*  
- Feature 2: *puy and sale books*  
- Feature 3: *custoimze your book*  


---

## Usage 
each end point will be discriped
### Authentication

| Method     | Endpoint              | Description                            |
| ---------- | --------------------- | -------------------------------------- |
| **POST**   | `/user/register/`      | Register a new user                    |
| **POST**   | `/user/login/`         | Login and get JWT tokens               |
| **POST**   | `/user/logout/`        | Logout (blacklist refresh token)       |
| **DELETE** | `/user/deleteaccount/` | Delete currently authenticated account |
| **GET**    | `/user/profile/`       | Get authenticated user profile         |

##Input (Request Body)
### Register
```json
request 
{
  "email": "user@example.com",
  "password": "12345678"
}
```
Output (Response)
```json
{
  "email": "user@example.com",
  "first_name": "Yara",
  "last_name": "Harby",
  "address": "Giza",
  "payment_info": "Visa 1234"
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
  "email": "user@example.com",
  "is_admin": false
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
Update Profile

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


### User Profile

| Method  | Endpoint              | Description                       |
| ------- | --------------------- | --------------------------------- |
| **GET** | `/user/updateprofile/` | Get profile data for update       |
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









