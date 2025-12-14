import fitz
import tempfile
import os
import io
import time
import shutil
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from PIL import Image
from .models import Book, Customizations
from .serializers import BookSerializer, CustomizationSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from user.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from gradio_client import Client, file
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse
from django.db.models import Q
from django.core.cache import cache

# ==================== CONSTANTS ====================
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff']
ALLOWED_PDF_TYPE = ['application/pdf']
GRADIO_TIMEOUT = 60
GRADIO_API_TIMEOUT = 45
MAX_RETRIES = 3

# ==================== VALIDATION FUNCTIONS ====================
def validate_file_size(file, max_size=MAX_UPLOAD_SIZE):
    """Validate file size"""
    if file.size > max_size:
        raise ValidationError(
            f"File too large. Max size is {max_size / (1024*1024)}MB"
        )

def validate_file_type(file, allowed_types):
    """Validate file MIME type"""
    if file.content_type not in allowed_types:
        raise ValidationError(
            f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )

# ==================== FILE VIEWS WITH STREAMING ====================
class BookFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        if not book.book_file:
            return HttpResponse("No file found", status=404)
        
        # Stream the file instead of loading it all at once
        file_stream = io.BytesIO(book.book_file)
        response = FileResponse(
            file_stream,
            content_type=book.book_file_type or "application/pdf"
        )
        response['Content-Disposition'] = f'inline; filename="{book.title}.pdf"'
        return response


class BookCoverView(APIView):
    """Serve book cover images"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        if not book.cover_image:
            return HttpResponse("No cover image found", status=404)
        
        # Stream the image
        file_stream = io.BytesIO(book.cover_image)
        response = FileResponse(
            file_stream,
            content_type=book.cover_image_type or "image/jpeg"
        )
        response['Content-Disposition'] = f'inline; filename="{book.title}_cover.jpg"'
        return response


class CustomBookFileView(APIView):
    """Serve customized book PDF files"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        customization = get_object_or_404(Customizations, pk=pk)
        
        if not customization.custom_book:
            return HttpResponse("File not found", status=404)
        
        # Stream the file
        file_stream = io.BytesIO(customization.custom_book)
        response = FileResponse(
            file_stream,
            content_type=customization.custom_book_type or "application/pdf"
        )
        response['Content-Disposition'] = f'attachment; filename="{customization.child_name}_{customization.book.title}.pdf"'
        return response


class CustomChildImageView(APIView):
    """Serve child images from customizations"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        customization = get_object_or_404(Customizations, pk=pk)
        
        if not customization.child_image:
            return HttpResponse("Child image not found", status=404)
        
        # Stream the image
        file_stream = io.BytesIO(customization.child_image)
        response = FileResponse(
            file_stream,
            content_type=customization.child_image_type or "image/jpeg"
        )
        response['Content-Disposition'] = f'inline; filename="{customization.child_name}_photo.jpg"'
        return response

# ==================== BOOK CUSTOMIZATION ====================
class CustomizeBook(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, format=None):
        temp_dir = None
        try:
            # Validate input
            book_id = request.data.get('book')
            child_name = request.data.get('child_name')
            child_image = request.FILES.get('child_image')
            user = request.user

            if not all([book_id, child_name, child_image]):
                return Response(
                    {"error": "book_id, child's name and child's image are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size and type
            try:
                validate_file_size(child_image, 10 * 1024 * 1024)  # 10MB for images
                validate_file_type(child_image, ALLOWED_IMAGE_TYPES)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            # Get book with select_related for optimization
            try:
                book = Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                return Response({"error": "Book not found"}, status=status.HTTP_404_NOT_FOUND)
            
            original_character_name = book.char_name if book.char_name else ""

            # Process child image
            child_image_binary = self.process_child_image_to_binary(child_image)
            if not child_image_binary:
                return Response(
                    {"error": "Invalid child image format."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            
            # Save book PDF
            book_path = os.path.join(temp_dir, "book_temp.pdf")
            if not book.book_file:
                return Response(
                    {"error": "Book file is missing."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with open(book_path, 'wb') as f:
                if isinstance(book.book_file, memoryview):
                    f.write(book.book_file.tobytes())
                else:
                    f.write(book.book_file)

            # Save child image
            child_image_path = os.path.join(temp_dir, "child_image.jpg")
            with open(child_image_path, 'wb') as f:
                f.write(child_image_binary)

            # Extract images from PDF
            images_info = self.extract_images_with_positions(book_path, temp_dir)
            if not images_info:
                return Response(
                    {"error": "No images found in the PDF"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            print(f"📸 Extracted {len(images_info)} images from PDF")
            
            # Process images
            processed_images_folder = os.path.join(temp_dir, "processed_images")
            os.makedirs(processed_images_folder, exist_ok=True)
            
            processed_images = {}
            client = self.initialize_gradio_client()
            
            if client:
                # Process with Gradio
                for i, img_info in enumerate(images_info):
                    print(f"  Processing image {i+1}/{len(images_info)}...")
                    processed_image = self.process_with_gradio_client_with_retry(
                        img_info['original_image_path'],
                        child_image_path,
                        temp_dir,
                        img_info['image_key'],
                        client
                    )
                    if processed_image:
                        processed_images[img_info['image_key']] = processed_image
                    else:
                        # Fallback to original
                        self.add_fallback_image(
                            img_info, processed_images_folder, processed_images, i
                        )
            else:
                # Fallback mode - use original images
                print("⚠️ Using fallback mode: Direct image replacement")
                for i, img_info in enumerate(images_info):
                    self.add_fallback_image(
                        img_info, processed_images_folder, processed_images, i
                    )

            # Ensure all images are PNG
            self.convert_all_to_png(processed_images, processed_images_folder)

            # Replace images in PDF
            images_replaced_pdf = os.path.join(temp_dir, "images_replaced.pdf")
            self.replace_all_images(book_path, images_info, processed_images_folder, images_replaced_pdf)

            # Replace character names
            final_pdf_path, character_replacements = self.replace_character_name(
                images_replaced_pdf, original_character_name, child_name, temp_dir
            )

            # Read final PDF
            with open(final_pdf_path, 'rb') as f:
                custom_book_binary = f.read()

            # Save customization
            customization = Customizations.objects.create(
                book=book,
                child_name=child_name,
                child_image=child_image_binary,
                child_image_type=self.get_image_mime_type(child_image),
                child_age=request.data.get('child_age', ''),
                custom_book=custom_book_binary,
                custom_book_type="application/pdf",
                user_id=user
            )

            return Response({
                "message": "Book customized successfully!",
                "child_name": child_name,
                "images_processed": len(processed_images),
                "total_images": len(images_info),
                "character_replacements": character_replacements,
                "character_replaced": character_replacements > 0,
                "original_character_name": original_character_name,
                "customization_id": customization.id,
                "book_title": book.title,
                "custom_book_url": request.build_absolute_uri(
                    reverse("custom-book-file", args=[customization.id])
                ),
                "ai_processing_used": client is not None,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Processing failed: {str(e)}")
            print(f"🔍 Error details:\n{error_details}")
            return Response({
                "error": "Processing failed",
                "details": str(e)[:200]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print("✅ Temporary files cleaned up")
                except Exception as cleanup_error:
                    print(f"⚠️ Cleanup error: {cleanup_error}")

    def initialize_gradio_client(self):
        """Initialize Gradio client with error handling"""
        try:
            print("🤖 Initializing Gradio Client...")
            client = Client(
                "shada-elewa/koko-land-demo",
                timeout=GRADIO_TIMEOUT,
                serialize=False
            )
            print("✅ Gradio Client initialized successfully")
            return client
        except Exception as e:
            print(f"❌ Failed to initialize Gradio Client: {str(e)}")
            return None

    def process_with_gradio_client_with_retry(self, book_image_path, child_image_path, 
                                               temp_dir, image_key, client):
        """Process with retry logic and exponential backoff"""
        for attempt in range(MAX_RETRIES):
            result = self.process_with_gradio_client(
                book_image_path, child_image_path, temp_dir, image_key, client
            )
            if result:
                return result
            
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                print(f"  ⏳ Retry {attempt + 1}/{MAX_RETRIES} after {wait_time}s...")
                time.sleep(wait_time)
        
        return None

    def add_fallback_image(self, img_info, processed_images_folder, processed_images, index):
        """Add fallback image (original) to processed images"""
        new_image_name = f"processed_{index:03d}.png"
        new_image_path = os.path.join(processed_images_folder, new_image_name)
        self.convert_to_png_if_needed(img_info['original_image_path'], new_image_path)
        processed_images[img_info['image_key']] = new_image_path

    def convert_all_to_png(self, processed_images, processed_images_folder):
        """Convert all processed images to PNG format"""
        for i, (image_key, image_path) in enumerate(processed_images.items()):
            new_image_name = f"processed_{i:03d}.png"
            new_image_path = os.path.join(processed_images_folder, new_image_name)
            if not os.path.exists(new_image_path):
                self.convert_to_png_if_needed(image_path, new_image_path)

    def process_with_gradio_client(self, book_image_path, child_image_path, temp_dir, image_key, client):
        """Process book image with child image using Gradio Client"""
        try:
            print(f"  🤖 Processing {image_key} with Gradio Client...")
            
            processed_book_image_path = self.process_book_image_for_gradio(
                book_image_path, temp_dir, image_key
            )
            if not processed_book_image_path or not os.path.exists(processed_book_image_path):
                print(f"  ❌ Processed book image not found for {image_key}")
                return None
            
            print(f"  🚀 Sending request to Gradio API...")
            
            try:
                import threading
                import queue
                
                result_queue = queue.Queue()
                
                def make_api_call():
                    try:
                        result = client.predict(
                            cartoon_img=file(processed_book_image_path),
                            kid_img=file(child_image_path),
                            api_name="/run_app"
                        )
                        result_queue.put(("success", result))
                    except Exception as e:
                        result_queue.put(("error", str(e)))
                
                api_thread = threading.Thread(target=make_api_call)
                api_thread.daemon = True
                api_thread.start()
                api_thread.join(timeout=GRADIO_API_TIMEOUT)
                
                if api_thread.is_alive():
                    print(f"  ⏱️ Gradio API timeout for {image_key}")
                    return None
                
                if result_queue.empty():
                    print(f"  ❌ No response from Gradio API for {image_key}")
                    return None
                
                status_result, result = result_queue.get()
                
                if status_result == "error":
                    print(f"  ❌ Gradio API error: {result}")
                    return None
                
                print(f"  📨 Gradio API response received")
                
                if not result:
                    print(f"  ❌ Empty result from Gradio API")
                    return None
                
                return self.handle_gradio_result(result, temp_dir, image_key)
                    
            except Exception as api_error:
                print(f"  ❌ Gradio API error: {str(api_error)}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error processing image {image_key}: {str(e)}")
            return None

    def handle_gradio_result(self, result, temp_dir, image_key):
        """Handle different types of Gradio API results"""
        processed_image_path = os.path.join(temp_dir, f"gradio_result_{image_key}.png")
        source_path = None
        
        if isinstance(result, str):
            if os.path.exists(result):
                source_path = result
            elif result.startswith('http'):
                source_path = self.download_image_from_url(result, temp_dir, image_key)
            else:
                print(f"  ❌ Unexpected string result: {result[:100]}...")
                return None
        elif isinstance(result, bytes):
            source_path = os.path.join(temp_dir, f"raw_result_{image_key}.png")
            with open(source_path, 'wb') as f:
                f.write(result)
        elif hasattr(result, '__iter__'):
            source_path = self.extract_from_iterable(result, temp_dir, image_key)
        else:
            print(f"  ❌ Unexpected result type: {type(result)}")
            return None
        
        if not source_path:
            return None
        
        # Verify and save image
        try:
            with Image.open(source_path) as img:
                img.verify()
            with Image.open(source_path) as img:
                img.save(processed_image_path, format='PNG')
            print(f"  ✅ Successfully saved processed image: {processed_image_path}")
            return processed_image_path
        except Exception as img_error:
            print(f"  ❌ Invalid image file: {str(img_error)}")
            return None

    def download_image_from_url(self, url, temp_dir, image_key):
        """Download image from URL"""
        print(f"  ⚠️ URL response received, downloading...")
        import requests
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                source_path = os.path.join(temp_dir, f"download_{image_key}.png")
                with open(source_path, 'wb') as f:
                    f.write(response.content)
                return source_path
            else:
                print(f"  ❌ Failed to download from URL: {response.status_code}")
                return None
        except Exception as download_error:
            print(f"  ❌ Download error: {str(download_error)}")
            return None

    def extract_from_iterable(self, result, temp_dir, image_key):
        """Extract file path or bytes from iterable result"""
        for item in result:
            if isinstance(item, str) and os.path.exists(item):
                return item
            elif isinstance(item, bytes):
                source_path = os.path.join(temp_dir, f"raw_result_{image_key}.png")
                with open(source_path, 'wb') as f:
                    f.write(item)
                return source_path
        print(f"  ❌ No valid result in iterable: {type(result)}")
        return None

    def process_child_image_to_binary(self, child_image):
        """Process child image and return as binary data"""
        try:
            child_image_data = child_image.read()
            print(f"👶 Child image size: {len(child_image_data)} bytes")
            
            img = Image.open(io.BytesIO(child_image_data))
            print(f"🖼️ Child image format: {img.format}, mode: {img.mode}, size: {img.size}")
            
            if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                img = img.convert('RGB')
            
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='JPEG', quality=95, optimize=True)
            processed_data = output_buffer.getvalue()
            print(f"✅ Child image processed: {len(processed_data)} bytes")
            return processed_data
            
        except Exception as e:
            print(f"❌ Error processing child image: {str(e)}")
            return None

    def get_image_mime_type(self, image_file):
        """Get MIME type from uploaded image"""
        try:
            image_file.seek(0)
            img = Image.open(image_file)
            format_to_mime = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'GIF': 'image/gif',
                'BMP': 'image/bmp',
                'TIFF': 'image/tiff',
                'WEBP': 'image/webp'
            }
            return format_to_mime.get(img.format.upper(), 'image/jpeg')
        except:
            return 'image/jpeg'

    def extract_images_with_positions(self, pdf_path, output_folder):
        """Extract all images from PDF with their positions and metadata"""
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        doc = fitz.open(pdf_path)
        images_info = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                image_instances = page.get_image_rects(xref)
                
                for instance_num, bbox in enumerate(image_instances):
                    img_filename = f"page_{page_num}_img_{img_index}_instance_{instance_num}.png"
                    img_path = os.path.join(output_folder, img_filename)
                    image_key = f"page_{page_num}_img_{img_index}_instance_{instance_num}"
                    
                    try:
                        if pix.n - pix.alpha < 4:
                            pix.save(img_path)
                        else:
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            pix1.save(img_path)
                            pix1 = None
                        
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
                        
                    except Exception as e:
                        print(f"  ⚠️ Failed to extract image {image_key}: {str(e)}")
                        continue
                
                pix = None
        
        doc.close()
        print(f"📸 Extracted {len(images_info)} images")
        return images_info

    def process_book_image_for_gradio(self, book_image_path, temp_dir, image_key):
        """Process book image to ensure compatibility with Gradio Client"""
        try:
            with Image.open(book_image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                
                max_size = 2048
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                processed_path = os.path.join(temp_dir, f"gradio_input_{image_key}.jpg")
                img.save(processed_path, format='JPEG', quality=95)
                return processed_path
                
        except Exception as e:
            print(f"    ❌ Error processing book image {image_key}: {str(e)}")
            return book_image_path

    def convert_to_png_if_needed(self, source_path, dest_path):
        """Convert any image format to PNG for consistency"""
        try:
            with Image.open(source_path) as img:
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                img.save(dest_path, format='PNG')
        except Exception as e:
            print(f"❌ Error converting image: {str(e)}")
            with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
                dst.write(src.read())

    def replace_all_images(self, pdf_path, images_info, new_images_folder, output_pdf_path):
        """Replaces all extracted images with new images from a folder"""
        try:
            doc = fitz.open(pdf_path)
            
            new_image_files = [f for f in os.listdir(new_images_folder) 
                             if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp'))]
            new_image_files.sort()
            
            if len(new_image_files) < len(images_info):
                print(f"⚠️ Only {len(new_image_files)} new images found for {len(images_info)} positions")
            
            for i, img_info in enumerate(images_info):
                if i < len(new_image_files):
                    new_image_path = os.path.join(new_images_folder, new_image_files[i])
                    page_num = img_info['page_num']
                    bbox = img_info['bbox']
                    
                    page = doc[page_num]
                    page.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1), overlay=False)
                    
                    try:
                        page.insert_image(bbox, filename=new_image_path)
                    except Exception as e:
                        print(f"❌ Failed to insert image {new_image_path}: {str(e)}")
                        page.draw_rect(bbox, color=(0.9, 0.9, 0.9), fill=(0.9, 0.9, 0.9), overlay=False)
            
            doc.save(output_pdf_path)
            doc.close()
            print(f"✅ PDF with replaced images saved: {output_pdf_path}")
        except Exception as e:
            print(f"❌ Error in replace_all_images: {str(e)}")
            raise

    def replace_character_name(self, images_replaced_pdf, original_character_name, child_name, temp_dir):
        """Replace character name in PDF using PyMuPDF"""
        if not original_character_name or original_character_name.strip() == "":
            print("⚠️ No original character name specified, skipping text replacement")
            return images_replaced_pdf, 0
            
        final_pdf_path = os.path.join(temp_dir, "final_customized.pdf")
        
        print(f"\n{'='*70}")
        print(f"TEXT REPLACEMENT - Using PyMuPDF")
        print(f"{'='*70}")
        print(f"Searching for: '{original_character_name}'")
        print(f"Replacing with: '{child_name}'")
        print(f"{'='*70}\n")
        
        self.diagnose_pdf_text(images_replaced_pdf, original_character_name)
        
        print("🔧 Attempting standard text replacement...")
        result = self.replace_text_in_pdf(
            images_replaced_pdf, original_character_name, child_name, final_pdf_path
        )
        
        if result["success"] and result["replacements"] > 0:
            print(f"✅ Text replacement successful: {result['replacements']} replacements")
            return final_pdf_path, result["replacements"]
        
        print("\n🔧 Attempting advanced redaction method...")
        result = self.advanced_text_replacement(
            images_replaced_pdf, original_character_name, child_name, final_pdf_path
        )
        
        if result["success"] and result["replacements"] > 0:
            print(f"✅ Advanced text replacement successful: {result['replacements']} replacements")
            return final_pdf_path, result["replacements"]
        
        print("\n⚠️ No text instances found - using PDF with replaced images only")
        shutil.copy2(images_replaced_pdf, final_pdf_path)
        return final_pdf_path, 0

    def diagnose_pdf_text(self, pdf_path, search_text):
        """Diagnose what text exists in the PDF"""
        try:
            doc = fitz.open(pdf_path)
            total_chars = 0
            found_pages = []
            
            print(f"📋 Analyzing {len(doc)} pages for text content...")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                total_chars += len(text)
                
                if search_text.lower() in text.lower():
                    found_pages.append(page_num + 1)
                    lines = [line for line in text.split('\n') if search_text.lower() in line.lower()]
                    print(f"\n✅ Found on page {page_num + 1}:")
                    for line in lines[:2]:
                        print(f"   '{line.strip()}'")
            
            doc.close()
            
            if found_pages:
                print(f"\n✅ Text '{search_text}' found on pages: {found_pages}")
            else:
                print(f"\n⚠️ Text '{search_text}' NOT found in PDF")
                print(f"   Total text characters in PDF: {total_chars}")
                if total_chars == 0:
                    print(f"   ⚠️ PDF contains NO extractable text (might be all images)")
                    
        except Exception as e:
            print(f"❌ Diagnosis error: {str(e)}")

    def replace_text_in_pdf(self, pdf_path, old_text, new_text, output_path):
        """Replace text in PDF using PyMuPDF standard method"""
        try:
            doc = fitz.open(pdf_path)
            total_replacements = 0
            pages_modified = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text_instances = page.search_for(old_text)
                
                if text_instances:
                    print(f"   Found {len(text_instances)} instance(s) on page {page_num + 1}")
                    pages_modified.append(page_num + 1)
                    
                    for rect in text_instances:
                        blocks = page.get_text("dict")["blocks"]
                        font_size = 12
                        
                        for block in blocks:
                            if block["type"] == 0:
                                for line in block["lines"]:
                                    for span in line["spans"]:
                                        span_rect = fitz.Rect(span["bbox"])
                                        if span_rect.intersects(rect):
                                            font_size = span["size"]
                                            break
                        
                        expanded_rect = rect + (-2, -2, 2, 2)
                        page.draw_rect(expanded_rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        if len(new_text) > len(old_text):
                            font_size = font_size * (len(old_text) / len(new_text))
                        
                        page.insert_text(
                            (rect.x0, rect.y0 + rect.height * 0.8),
                            new_text,
                            fontsize=font_size,
                            fontname="helv",
                            color=(0, 0, 0)
                        )
                        total_replacements += 1
            
            if total_replacements > 0:
                doc.save(output_path, garbage=4, deflate=True, clean=True)
                doc.close()
                return {
                    "success": True,
                    "replacements": total_replacements,
                    "pages_modified": pages_modified
                }
            else:
                doc.close()
                return {"success": False, "replacements": 0}
                
        except Exception as e:
            print(f"❌ Text replacement error: {str(e)}")
            return {"success": False, "replacements": 0, "error": str(e)}

    def advanced_text_replacement(self, pdf_path, old_text, new_text, output_path):
        """Advanced text replacement using redaction annotations"""
        try:
            doc = fitz.open(pdf_path)
            total_replacements = 0
            
            search_variations = list(set([
                old_text, old_text.strip(), old_text.lower(), 
                old_text.upper(), old_text.title()
            ]))
            
            print(f"   Trying variations: {search_variations}")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for search_text in search_variations:
                    areas = page.search_for(search_text)
                    
                    for area in areas:
                        page.add_redact_annot(
                            area, text=new_text, fontsize=11,
                            fill=(1, 1, 1), text_color=(0, 0, 0)
                        )
                        total_replacements += 1
                
                page.apply_redactions()
            
            if total_replacements > 0:
                doc.save(output_path, garbage=4, deflate=True)
                doc.close()
                print(f"   Redaction method: {total_replacements} replacements")
                return {"success": True, "replacements": total_replacements}
            else:
                doc.close()
                return {"success": False, "replacements": 0}
                
        except Exception as e:
            print(f"❌ Advanced replacement error: {str(e)}")
            return {"success": False, "replacements": 0, "error": str(e)}


# ==================== BOOK CRUD OPERATIONS ====================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listCustomizedBooks(request):
    """List all customized books with optimized query"""
    if request.method == "GET":
        customized_books = Customizations.objects.select_related(
            'book', 'user_id'
        ).all()
        
        serializer = CustomizationSerializer(
            customized_books, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def addbook(request):
    """Add a new book with file validation"""
    if request.method == "POST":
        book_file = request.FILES.get('book_file')
        cover_image = request.FILES.get('cover_image')
        
        if not book_file:
            return Response(
                {"error": "Book PDF file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate files
        try:
            validate_file_size(book_file)
            validate_file_type(book_file, ALLOWED_PDF_TYPE)
            
            if cover_image:
                validate_file_size(cover_image, 10 * 1024 * 1024)  # 10MB
                validate_file_type(cover_image, ALLOWED_IMAGE_TYPES)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Read files as binary
        book_file_data = book_file.read()
        
        book_data = {
            'title': request.data.get('title'),
            'char_name': request.data.get('char_name', ''),
            'price': request.data.get('price', 0),
            'category': request.data.get('category', ''),
            'age': request.data.get('age', ''),
            'gender': request.data.get('gender', ''),
            'rate': request.data.get('rate', 0),
            'description': request.data.get('description', ''),
            'book_file': book_file_data,
            'book_file_type': book_file.content_type or 'application/pdf',
        }
        
        if cover_image:
            cover_image_data = cover_image.read()
            book_data['cover_image'] = cover_image_data
            book_data['cover_image_type'] = cover_image.content_type or 'image/jpeg'
        
        try:
            book = Book.objects.create(**book_data)
            serializer = BookSerializer(book, context={"request": request})
            
            return Response({
                "msg": "Book added successfully",
                "data": serializer.data,
                "book_file_url": request.build_absolute_uri(
                    reverse("book-file", args=[book.id])
                ),
                "cover_image_url": request.build_absolute_uri(
                    reverse("book-cover", args=[book.id])
                ) if book.cover_image else None
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_books(request):
    """List all books"""
    if request.method == "GET":
        books = Book.objects.all()
        serializer = BookSerializer(books, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def retrieve_one_book(request, pk):
    """Retrieve a single book with caching"""
    if request.method == "GET":
        cache_key = f"book_{pk}"
        book_data = cache.get(cache_key)
        
        if not book_data:
            try:
                book = Book.objects.get(pk=pk)
                serializer = BookSerializer(book, context={"request": request})
                book_data = serializer.data
                cache.set(cache_key, book_data, 3600)  # Cache for 1 hour
            except Book.DoesNotExist:
                return Response(
                    {"msg": "Not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(book_data, status=status.HTTP_200_OK)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_book(request, pk):
    """Update a book"""
    if request.method == "PATCH":
        try:
            book = Book.objects.get(pk=pk)
            serializer = BookSerializer(
                book, data=request.data, partial=True, context={"request": request}
            )
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                # Invalidate cache
                cache.delete(f"book_{pk}")
                return Response({
                    "msg": "Book updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Book.DoesNotExist:
            return Response({"msg": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_book(request, pk):
    """Delete a book"""
    if request.method == "DELETE":
        try:
            book = Book.objects.get(pk=pk)
            book.delete()
            # Invalidate cache
            cache.delete(f"book_{pk}")
            return Response(
                {"msg": "Deleted successfully"}, 
                status=status.HTTP_204_NO_CONTENT
            )
        except Book.DoesNotExist:
            return Response(
                {"error": "Book not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def search_about_book(request):
    """Search books with multiple criteria support"""
    if request.method == "POST":
        title = request.data.get("title")
        category = request.data.get("category")
        age = request.data.get("age")
        gender = request.data.get("gender")

        if not any([title, category, age, gender]):
            return Response(
                {"msg": "At least one search parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build dynamic query with Q objects for combined search
        query = Q()
        if title:
            query &= Q(title__icontains=title)
        if category:
            query &= Q(category__icontains=category)
        if age:
            query &= Q(age__icontains=age)
        if gender:
            query &= Q(gender__icontains=gender)

        books = Book.objects.filter(query)
        
        if not books.exists():
            return Response(
                {"msg": "No books found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BookSerializer(books, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    return Response(
        {"msg": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )