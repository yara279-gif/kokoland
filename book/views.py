import fitz
import tempfile
import os
import io
import requests
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from PIL import Image
from .models import Book, Customizations
from rest_framework import generics
from .serializers import BookSerializer, CustomizationSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from user.models import User
from django.core.exceptions import ObjectDoesNotExist


class CustomizeBook(APIView):
    # PDF.co API configuration
    PDF_CO_API_KEY = "yaraharby4@gmail.com_BVVd7y05dquQ4Uop9MdyE5yARXYoc2Sjl4yVqyjy72RBvpXLbzGdPWUb9gGMxweT"
    PDF_CO_BASE_URL = "https://api.pdf.co/v1"

    def post(self, request, format=None):
        try:
            book_id = request.data.get('book')
            child_name = request.data.get('child_name')
            child_image = request.FILES.get('child_image')
            user_id = request.data.get('user_id')
            
  
            if not book_id or not child_name or not child_image or not user_id :
                return Response(
                    {"error": "book_id, child's name and child's image are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get book object
            book = Book.objects.get(id=book_id)
            book_path = book.book_file.path
            original_character_name = book.char_name
            
            # Read and validate child image
            child_image_data = self.process_child_image(child_image)
            if not child_image_data:
                return Response(
                    {"error": "Invalid child image format. Supported formats: JPEG, PNG, WebP"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            
            # Create a temporary directory to store modified PDF
            with tempfile.TemporaryDirectory() as temp_dir:

                # Extract all images from PDF with their positions
                images_info = self.extract_images_with_positions(book_path, temp_dir)

                if not images_info:
                    return Response(
                        {"error": "No images found in the PDF"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Process each image through AI model
                processed_images = {}
                for i, img_info in enumerate(images_info):
                    processed_image = self.process_with_ai_model(
                        img_info['original_image_path'], 
                        child_image_data,
                        temp_dir,
                        img_info['image_key']
                    )
                    if processed_image:
                        processed_images[img_info['image_key']] = processed_image
                        print(f"✅ Successfully processed image {img_info['image_key']}")
                    else:
                        print(f"❌ Failed to process image {img_info['image_key']}")

                
                # Create a folder for processed images
                processed_images_folder = os.path.join(temp_dir, "processed_images")
                os.makedirs(processed_images_folder, exist_ok=True)
                
                # Copy processed images to the folder with sequential names
                processed_image_files = []
                for i, (image_key, image_path) in enumerate(processed_images.items()):
                    new_image_name = f"processed_{i:03d}.png"
                    new_image_path = os.path.join(processed_images_folder, new_image_name)
                    
                    # Copy the file
                    with open(image_path, 'rb') as src, open(new_image_path, 'wb') as dst:
                        dst.write(src.read())
                    processed_image_files.append(new_image_name)
                
                # Step 1: Replace images in PDF
                images_replaced_pdf = os.path.join(temp_dir, "images_replaced.pdf")
                self.replace_all_images(
                    book_path, 
                    images_info, 
                    processed_images_folder, 
                    images_replaced_pdf
                )
                
                # Step 2: Replace character names using PDF.co API
                final_pdf_path = os.path.join(temp_dir, "final_customized.pdf")
                
                # Upload the PDF to PDF.co
                uploaded_file_url = self.upload_file_to_pdfco(images_replaced_pdf)
                if not uploaded_file_url:
                    return Response(
                        {"error": "Failed to upload PDF for text replacement"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # Replace text using PDF.co API
                replacement_success = self.replace_text_via_pdfco(
                    uploaded_file_url, 
                    original_character_name, 
                    child_name, 
                    final_pdf_path
                )
                
                if not replacement_success:
                    # Fallback: use the image-replaced PDF without text replacement
                    print("⚠️ Text replacement failed, using image-replaced PDF as fallback")
                    final_pdf_path = images_replaced_pdf
                    character_replacements = 0
                else:
                    character_replacements = 1  # PDF.co doesn't return count, so we assume success
                    print("✅ Character names replaced successfully using PDF.co API")
                
                # Save the customized PDF
                with open(final_pdf_path, 'rb') as f:
                    pdf_content = f.read()
                
                # Create customized file
                custom_book = ContentFile(
                    pdf_content, 
                    name=f"customized_{child_name}_{book.title}.pdf"
                )
                
                # Fetch User instance
                try:
                    user = User.objects.get(id=int(user_id))
                except (ValueError, ObjectDoesNotExist):
                    return Response(
                        {"error": "Invalid or non-existent user_id."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Save to Customizations model
                customization = Customizations.objects.create(
                    book=book,
                    child_name=child_name,
                    child_image=child_image,
                    child_age=request.data.get('child_age', ''),
                    custom_book=custom_book,
                    user_id=user

                )

                
                return Response({
                    "message": "Book customized successfully!",
                    "child_name": child_name,
                    "images_processed": len(processed_images),
                    "total_images": len(images_info),
                    "character_replaced": character_replacements > 0,
                    "original_character_replaced": original_character_name,
                    "custom_book_url": customization.custom_book.url,
                    "customization_id": customization.id,
                    "book_title": book.title
                }, status=status.HTTP_200_OK)
                
        except Book.DoesNotExist:
            return Response(
                {"error": "Book not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Overall processing error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": f"Processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def upload_file_to_pdfco(self, file_path):
        """Uploads file to PDF.co cloud storage"""
        try:
            api_url = f"{self.PDF_CO_BASE_URL}/file/upload/get-presigned-url"
            params = {
                "name": os.path.basename(file_path),
                "contenttype": "application/octet-stream"
            }
            
            headers = {
                "x-api-key": self.PDF_CO_API_KEY
            }
            
            print(f"📤 Uploading file to PDF.co: {file_path}")
            response = requests.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                json_data = response.json()
                if not json_data.get("error", False):
                    upload_url = json_data["presignedUrl"]
                    uploaded_file_url = json_data["url"]
                    
                    # Upload the file
                    with open(file_path, 'rb') as file:
                        upload_response = requests.put(
                            upload_url, 
                            data=file, 
                            headers={"content-type": "application/octet-stream"}
                        )
                    
                    if upload_response.status_code == 200:
                        print(f"✅ File uploaded successfully: {uploaded_file_url}")
                        return uploaded_file_url
                    else:
                        print(f"❌ Upload failed: {upload_response.status_code}")
                else:
                    print(f"❌ PDF.co API error: {json_data.get('message', 'Unknown error')}")
            else:
                print(f"❌ Request failed: {response.status_code} {response.reason}")
            
            return None
            
        except Exception as e:
            print(f"❌ Error uploading to PDF.co: {str(e)}")
            return None

    def replace_text_via_pdfco(self, uploaded_file_url, old_value, new_value, destination_file):
        """Replaces text in PDF using PDF.co API"""
        try:
            api_url = f"{self.PDF_CO_BASE_URL}/pdf/edit/replace-text"
            
            headers = {
                "x-api-key": self.PDF_CO_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "name": os.path.basename(destination_file),
                "password": "",  # No password
                "url": uploaded_file_url,
                "searchString": old_value,
                "replaceString": new_value +" ",
                "caseSensitive": False,  # Case insensitive replacement
                "regexSearch": False     # Exact text search
            }
            
            print(f"🔄 Replacing '{old_value}' with '{new_value}' via PDF.co API...")
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                json_data = response.json()
                if not json_data.get("error", False):
                    result_file_url = json_data["url"]
                    
                    # Download the result file
                    download_response = requests.get(result_file_url, stream=True)
                    
                    if download_response.status_code == 200:
                        # Ensure destination directory exists
                        os.makedirs(os.path.dirname(destination_file), exist_ok=True)
                        
                        with open(destination_file, 'wb') as file:
                            for chunk in download_response.iter_content(chunk_size=8192):
                                file.write(chunk)
                        
                        print(f"✅ Result file saved: {destination_file}")
                        return True
                    else:
                        print(f"❌ Download failed: {download_response.status_code}")
                else:
                    print(f"❌ PDF.co replacement error: {json_data.get('message', 'Unknown error')}")
            else:
                print(f"❌ Request failed: {response.status_code} {response.reason}")
            
            return False
            
        except Exception as e:
            print(f"❌ Error in PDF.co text replacement: {str(e)}")
            return False

    # ... keep all your existing methods the same (process_child_image, extract_images_with_positions, etc.)
    def process_child_image(self, child_image):
        """Process and validate child image, convert to appropriate format"""
        try:
            # Read the image
            child_image_data = child_image.read()
            print(f"👶 Child image size: {len(child_image_data)} bytes")
            
            # Validate image format using PIL
            with Image.open(io.BytesIO(child_image_data)) as img:
                print(f"🖼️ Child image format: {img.format}, mode: {img.mode}, size: {img.size}")
                
                # Convert to RGB if necessary (removes alpha channel)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                    print("🔄 Converted child image to RGB")
                
                # Save as JPEG for better compatibility
                output_buffer = io.BytesIO()
                img.save(output_buffer, format='JPEG', quality=95)
                processed_data = output_buffer.getvalue()
                print(f"💾 Processed child image size: {len(processed_data)} bytes")
                return processed_data
                
        except Exception as e:
            print(f"❌ Error processing child image: {str(e)}")
            return None

    def extract_images_with_positions(self, pdf_path, output_folder):
        """
        Extract all images from PDF with their positions and metadata
        """
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        doc = fitz.open(pdf_path)
        images_info = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get all images on the page
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                # Extract image information
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                
                # Get image position (bounding box)
                image_instances = page.get_image_rects(xref)
                
                for instance_num, bbox in enumerate(image_instances):
                    # Generate unique filename and key
                    img_filename = f"page_{page_num}_img_{img_index}_instance_{instance_num}.png"
                    img_path = os.path.join(output_folder, img_filename)
                    image_key = f"page_{page_num}_img_{img_index}_instance_{instance_num}"
                    
                    # Save the image
                    if pix.n - pix.alpha < 4:  # this is GRAY or RGB
                        pix.save(img_path)
                    else:  # CMYK: convert to RGB first
                        pix1 = fitz.Pixmap(fitz.csRGB, pix)
                        pix1.save(img_path)
                        pix1 = None
                    
                    # Store image information
                    image_info = {
                        'page_num': page_num,
                        'image_index': img_index,
                        'instance_num': instance_num,
                        'bbox': bbox,
                        'original_image_path': img_path,
                        'image_key': image_key,
                        'xref': xref
                    }
                    images_info.append(image_info)
                
                pix = None  # free pixmap resources
        
        doc.close()
        
        print(f"Extracted {len(images_info)} images to {output_folder}")
        return images_info

    def process_with_ai_model(self, book_image_path, child_image_data, temp_dir, image_key):
        """Send book image and child image to AI model and get processed image"""
        try:
            FASTAPI_URL = "https://homelessly-spathic-eddie.ngrok-free.dev/api/face-transfer/upload"
            
            print(f"  🤖 Sending {image_key} to AI model...")
            
            # Process book image to ensure compatibility
            processed_book_image_path = self.process_book_image_for_api(book_image_path, temp_dir, image_key)
            if not processed_book_image_path:
                print(f"  ❌ Failed to process book image for {image_key}")
                return None
            
            # Get file sizes for debugging
            book_file_size = os.path.getsize(processed_book_image_path)
            child_file_size = len(child_image_data)
            print(f"  📊 File sizes - Book: {book_file_size} bytes, Child: {child_file_size} bytes")
            
            # Prepare files for sending with proper content types
            with open(processed_book_image_path, 'rb') as book_img_file:
                files = {
                    'target_image': ('target_image.jpg', book_img_file, 'image/jpeg'),
                    'source_image': ('source_image.jpg', child_image_data, 'image/jpeg')
                }
                
                data = {'model': 'inswapper_128'}
                
                print(f"  🚀 Sending request to FastAPI...")
                
                response = requests.post(FASTAPI_URL, files=files, data=data, timeout=60)
                print(f"  📨 FastAPI response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        test_img = Image.open(io.BytesIO(response.content))
                        print(f"  ✅ Valid image response: {test_img.format}, {test_img.size}")
                        
                        processed_image_path = os.path.join(temp_dir, f"processed_{image_key}.png")
                        with open(processed_image_path, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"  💾 Saved processed image: {processed_image_path}")
                        return processed_image_path
                    except Exception as img_error:
                        print(f"  ❌ Invalid image response: {str(img_error)}")
                        return None
                else:
                    print(f"  ❌ AI model error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"  ❌ Error processing image {image_key}: {str(e)}")
            return None

    def process_book_image_for_api(self, book_image_path, temp_dir, image_key):
        """Process book image to ensure compatibility with AI model"""
        try:
            with Image.open(book_image_path) as img:
                print(f"    📖 Book image original - format: {img.format}, mode: {img.mode}, size: {img.size}")
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                    print(f"    🔄 Converted book image to RGB")
                
                processed_path = os.path.join(temp_dir, f"processed_book_{image_key}.jpg")
                img.save(processed_path, format='JPEG', quality=95)
                print(f"    💾 Saved processed book image: {processed_path}")
                return processed_path
                
        except Exception as e:
            print(f"    ❌ Error processing book image {image_key}: {str(e)}")
            return book_image_path

    def replace_all_images(self, pdf_path, images_info, new_images_folder, output_pdf_path):
        """
        Replaces all extracted images with new images from a folder.
        """
        doc = fitz.open(pdf_path)
        
        # Get list of new image files
        new_image_files = [f for f in os.listdir(new_images_folder) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp'))]
        new_image_files.sort()
        
        # Check if we have enough replacement images
        if len(new_image_files) < len(images_info):
            print(f"Warning: Only {len(new_image_files)} new images found, but {len(images_info)} images need replacement.")
            print("Some images will not be replaced.")
        
        # Replace each image
        for i, img_info in enumerate(images_info):
            if i < len(new_image_files):
                new_image_path = os.path.join(new_images_folder, new_image_files[i])
                page_num = img_info['page_num']
                bbox = img_info['bbox']
                
                page = doc[page_num]
                
                # Remove the old image by drawing a white rectangle over it
                page.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1), overlay=False)
                
                # Insert the new image at the same position
                page.insert_image(bbox, filename=new_image_path)
                
                print(f"Replaced image on page {page_num} at position {bbox}")
            else:
                print(f"No replacement image available for image {i} on page {img_info['page_num']}")
        
        doc.save(output_pdf_path)
        doc.close()
        print(f"PDF with replaced images saved to {output_pdf_path}")
#===============================================================================================

@api_view(["GET"])
def listCustomizedBooks(request):
    if request.method == "GET":
        permission_classes = [IsAuthenticated]
        customized_books = Customizations.objects.all()

        serializer = CustomizationSerializer(customized_books, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response({"msg": "not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

#=========================================add book=================================================




@api_view(["POST"])
def addbook(request):
    if request.method == "POST":
        
        permission_classes = [IsAuthenticated]
        request.data["avilable"] = True
        serializer = BookSerializer(data=request.data, context={"request": request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(
                {"msg": "Book added successfull", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ++++++++++++++++++++++++++++++++++++(retrive_all_books)+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@api_view(["GET"])
def list_books(request):
    if request.method == "GET":
        permission_classes = [IsAuthenticated]
        books = Book.objects.all()

        serializer = BookSerializer(books, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response({"msg": "not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


# # ++++++++++++++++++++++++++++++++++++(retrive_one_book)+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@api_view(["GET"])
def retrieve_one_book(request, pk):
    if request.method == "GET":
        permission_classes = [IsAuthenticated]
        try:
            book = Book.objects.get(pk=pk)
            serializer = BookSerializer(book, context={"request": request})

            return Response(serializer.data, status=status.HTTP_200_OK)
        except Book.DoesNotExist:
            return Response({"msg": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({"msg": "not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


# # ++++++++++++++++++++++++++++++++++++(update_book)+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@api_view(["PATCH"])
def update_book(request, pk):
    if request.method == "PATCH":
        permission_classes = [IsAuthenticated]
        try:
            book = Book.objects.get(pk=pk)
            serializer = BookSerializer(
                book, data=request.data, partial=True, context={"request": request}
            )
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(
                    {"msg": "Book updated successfully", "data": serializer.data},
                    status=status.HTTP_200_OK,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Book.DoesNotExist:
            return Response({"msg": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"msg": "not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


# # ++++++++++++++++++++++++++++++++++++(delete_book)+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@api_view(["DELETE"])
def delete_book(request, pk):
    if request.method == "DELETE":
        try:
            book = Book.objects.get(pk=pk)
            book.delete()
            return Response(
                {"msg": "deleted successfully"}, status=status.HTTP_204_NO_CONTENT
            )
        except Book.DoesNotExist:
            return Response(
                {"error": "Book not found"}, status=status.HTTP_400_BAD_REQUEST
            )


# # ++++++++++++++++++++++++++++++++++++(search_about_book)+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@api_view(["POST"])
def search_about_book(request, title=None, category=None, age=None, gender=None):
    if request.method == "POST":
        permission_classes = [IsAuthenticated]
        title = request.data.get("title")
        category = request.data.get("category")
        age = request.data.get("age")
        gender = request.data.get("gender")

        if title is None and category is None and age is None and gender is None:
            return Response(
                {"msg": "At least one search parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if title:
                book = Book.objects.filter(title__icontains=title)
            elif category:
                book = Book.objects.filter(category__icontains=category)
            elif age:
                book = Book.objects.filter(age__icontains=age)
            elif gender:
                book = Book.objects.filter(gender__icontains=gender)
            serializer = BookSerializer(
                book, many=True, context={"request": request}
            )
            if serializer.data:
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"msg": "No books found"}, status=status.HTTP_404_NOT_FOUND
                )
        except Book.DoesNotExist as e:
            return Response(
                {"error": f"Book not found {e}"}, status=status.HTTP_404_NOT_FOUND
            )
    return Response({"msg": "not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)





