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
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse
from django.db.models import Q
from django.core.cache import cache
from gradio_client import Client, file 
from django.urls import reverse



# ==================== CONSTANTS ====================
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff']
ALLOWED_PDF_TYPE = ['application/pdf']
GRADIO_TIMEOUT = 120  # Increased timeout for AI model
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


# ==================== MAIN CUSTOMIZATION ENDPOINT ====================

class CustomizeBook(APIView):
    """
    Main endpoint to customize a book with AI-processed images and name replacement
    POST /books/customize/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, format=None):
        temp_dir = None
        try:
            # ===== STEP 0: VALIDATE INPUT =====
            book_id = request.data.get('book')
            child_name = request.data.get('child_name')
            child_image = request.FILES.get('child_image')
            user = request.user

            if not all([book_id, child_name, child_image]):
                return Response(
                    {"error": "book_id, child_name and child_image are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get book
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

            # ===== STEP 1: EXTRACT IMAGES FROM PDF =====
            print("\n" + "="*70)
            print("STEP 1: EXTRACTING IMAGES FROM PDF")
            print("="*70)
            images_info = self.extract_images_with_positions(book_path, temp_dir)
            if not images_info:
                return Response(
                    {"error": "No images found in the PDF"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            print(f"✅ Extracted {len(images_info)} images from PDF\n")
            
            # ===== STEP 2: PROCESS IMAGES WITH AI =====
            print("="*70)
            print("STEP 2: PROCESSING IMAGES WITH AI MODEL")
            print("="*70)
            processed_images_folder = os.path.join(temp_dir, "processed_images")
            os.makedirs(processed_images_folder, exist_ok=True)
            
            processed_images = {}
            
            for i, img_info in enumerate(images_info):
                print(f"\nProcessing image {i+1}/{len(images_info)}: {img_info['image_key']}")
                
                # Call AI model for this image
                ai_processed_path = self.process_with_gradio_client(
                    img_info['original_image_path'],
                    child_image_path,
                    temp_dir,
                    img_info['image_key']
                )
                
                # Determine which image to use
                if ai_processed_path and os.path.exists(ai_processed_path):
                    final_image_path = ai_processed_path
                    print(f"✅ Using AI-processed image")
                else:
                    final_image_path = img_info['original_image_path']
                    print(f"⚠️ Using original image (AI processing failed)")
                
                # Save to processed folder
                new_image_name = f"processed_{i:03d}.png"
                new_image_path = os.path.join(processed_images_folder, new_image_name)
                
                # Convert to PNG if needed
                self.convert_to_png_if_needed(final_image_path, new_image_path)
                
                processed_images[img_info['image_key']] = new_image_path
            
            print(f"\n✅ Processed {len(processed_images)} images")

            # ===== STEP 3: REPLACE IMAGES IN PDF =====
            print("\n" + "="*70)
            print("STEP 3: REPLACING IMAGES IN PDF")
            print("="*70)
            images_replaced_pdf = os.path.join(temp_dir, "images_replaced.pdf")
            self.replace_all_images(book_path, images_info, processed_images_folder, images_replaced_pdf)
            print(f"✅ Images replaced in PDF")

            # ===== STEP 4: REPLACE CHARACTER NAME =====
            print("\n" + "="*70)
            print("STEP 4: REPLACING CHARACTER NAME")
            print("="*70)
            
            if original_character_name:
                self.diagnose_pdf_text(images_replaced_pdf, original_character_name)
            
            final_pdf_path, character_replacements = self.replace_character_name_preserve_format(
                images_replaced_pdf, original_character_name, child_name, temp_dir
            )
            print(f"✅ Character name replaced: {character_replacements} instances")

            # ===== STEP 5: SAVE TO DATABASE =====
            with open(final_pdf_path, 'rb') as f:
                custom_book_binary = f.read()

            customization = Customizations.objects.create(
                book=book,
                child_name=child_name,
                child_image=child_image_binary,
                child_image_type=self.get_image_mime_type(child_image),
                child_age=request.data.get('child_age', ''),
                custom_book=custom_book_binary,
                custom_book_type="application/pdf",
                user=user
            )

            # Build URLs
            base_url = request.build_absolute_uri('/').rstrip('/')
            custom_book_url = f"{base_url}/books/customizations/{customization.id}/file/"
            child_image_url = f"{base_url}/books/customizations/{customization.id}/child-image/"

            print("\n" + "="*70)
            print("✅ CUSTOMIZATION COMPLETE")
            print("="*70)

            return Response({
                "success": True,
                "message": "Book customized successfully!",
                "customization_id": customization.id,
                "book_id": book.id,
                "book_title": book.title,
                "child_name": child_name,
                "images_processed": len(processed_images),
                "total_images": len(images_info),
                "character_replacements": character_replacements,
                "character_replaced": character_replacements > 0,
                "original_character_name": original_character_name,
                "custom_book_url": custom_book_url,
                "child_image_url": child_image_url,
                "ai_processing_used": any('ai_final' in processed_images.get(key, '') for key in processed_images),
                "created_at": customization.created_at.isoformat() if hasattr(customization, 'created_at') else None
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Processing failed: {str(e)}")
            print(f"🔍 Error details:\n{error_details}")
            return Response({
                "success": False,
                "error": "Processing failed",
                "details": str(e)[:300]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print("✅ Temporary files cleaned up")
                except Exception as cleanup_error:
                    print(f"⚠️ Cleanup error: {cleanup_error}")

    # ==================== AI IMAGE PROCESSING ====================

    def process_with_gradio_client(self, book_image_path, child_image_path, temp_dir, image_key):
        """
        Process book image with child image using Gradio AI model
        EXACT implementation based on provided documentation
        """
        try:
            print(f"\n🤖 AI PROCESSING: {image_key}")
            
            # ===== STEP 1: PREPARE IMAGES =====
            print("🖼️  Step 1: Preparing images...")
            
            # Prepare book image (Input 0: cartoon_img)
            prepared_book_image = self._prepare_book_image_for_ai(book_image_path, temp_dir, image_key)
            if not prepared_book_image:
                print("❌ Failed to prepare book image")
                return None
            
            # Prepare child image (Input 1: kid_img)  
            prepared_child_image = self._prepare_child_image_for_ai(child_image_path, temp_dir, image_key)
            if not prepared_child_image:
                print("❌ Failed to prepare child image")
                return None
            
            print(f"✅ Images prepared")
            
            # ===== STEP 2: CONNECT TO AI MODEL =====
            print("🔌 Step 2: Connecting to AI model...")
            
            try:
                # EXACTLY as per documentation - NO timeout parameter
                client = Client("shada-elewa/koko-land-demo")
                print("✅ Connected to AI model successfully")
            except Exception as e:
                print(f"❌ Failed to connect to AI model: {str(e)}")
                print("💡 The Hugging Face space might be sleeping. Visit: https://huggingface.co/spaces/shada-elewa/koko-land-demo")
                return None
            
            # ===== STEP 3: SEND REQUEST =====
            print("📤 Step 3: Sending request to AI model...")
            
            try:
                # EXACTLY as per documentation
                result = client.predict(
                    cartoon_img=file(prepared_book_image),  # Input 0
                    kid_img=file(prepared_child_image),     # Input 1
                    api_name="/run_app"                     # API endpoint
                )
                
                print(f"✅ AI model responded: {result}")
                
            except Exception as e:
                print(f"❌ AI request failed: {str(e)}")
                return None
            
            # ===== STEP 4: PROCESS RESULT =====
            print("📥 Step 4: Processing AI result...")
            
            # Handle the result
            processed_image_path = self._handle_ai_result(result, temp_dir, image_key)
            
            if processed_image_path and os.path.exists(processed_image_path):
                print(f"✅ AI processing complete!")
                return processed_image_path
            else:
                print("❌ Failed to process AI result")
                return None
                
        except Exception as e:
            print(f"❌ Unexpected error in AI processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _prepare_book_image_for_ai(self, book_image_path, temp_dir, image_key):
        """
        Prepare book page image for AI model
        Input 0 (cartoon_img): The background book page
        Format: JPG/PNG (AI will resize to 512x512 internally)
        """
        try:
            with Image.open(book_image_path) as img:
                print(f"   📖 Original book image: {img.format}, {img.size}")
                
                # Convert to RGB if needed
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # AI will resize to 512x512 internally, but ensure not too large
                max_size = 2048
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save as JPG
                output_path = os.path.join(temp_dir, f"ai_input_book_{image_key}.jpg")
                img.save(output_path, format='JPEG', quality=95)
                
                print(f"   ✅ Prepared book image: {output_path}")
                return output_path
                
        except Exception as e:
            print(f"   ❌ Error preparing book image: {str(e)}")
            return None

    def _prepare_child_image_for_ai(self, child_image_path, temp_dir, image_key):
        """
        Prepare child photo for AI model
        Input 1 (kid_img): The photo of the child
        Recommendation: Close-up photo, good lighting, no glasses/hats
        """
        try:
            with Image.open(child_image_path) as img:
                print(f"   👶 Original child image: {img.format}, {img.size}")
                
                # Convert to RGB if needed
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # For best results: close-up photo
                width, height = img.size
                
                # If image is very wide, crop to center square
                if width > height * 1.5:
                    crop_left = (width - height) // 2
                    img = img.crop((crop_left, 0, crop_left + height, height))
                elif height > width * 1.5:
                    crop_top = (height - width) // 2
                    img = img.crop((0, crop_top, width, crop_top + width))
                
                # Resize to reasonable size
                target_size = 1024
                if max(img.size) > target_size:
                    ratio = target_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save as JPG
                output_path = os.path.join(temp_dir, f"ai_input_child_{image_key}.jpg")
                img.save(output_path, format='JPEG', quality=95, optimize=True)
                
                print(f"   ✅ Prepared child image: {output_path}")
                return output_path
                
        except Exception as e:
            print(f"   ❌ Error preparing child image: {str(e)}")
            return None

    def _handle_ai_result(self, result, temp_dir, image_key):
        """
        Handle the result from AI model
        Output: returns a path/URL to the processed .webp or .jpg image
        """
        try:
            print(f"   🔍 Processing AI result of type: {type(result)}")
            
            # ===== CASE 1: Simple string (local file path) =====
            if isinstance(result, str):
                print(f"   Result: {result}")
                
                if os.path.exists(result):
                    print(f"   ✅ Found local file")
                    return self._convert_ai_output_to_png(result, temp_dir, image_key)
                elif result.startswith(('http://', 'https://')):
                    print(f"   🌐 Found URL")
                    downloaded_path = self._download_ai_result(result, temp_dir, image_key)
                    if downloaded_path:
                        return self._convert_ai_output_to_png(downloaded_path, temp_dir, image_key)
                else:
                    print(f"   ❌ String is not a valid file or URL")
            
            # ===== CASE 2: Bytes object =====
            elif isinstance(result, bytes):
                print(f"   Result is bytes, length: {len(result)}")
                
                # Try to save as image file
                output_path = os.path.join(temp_dir, f"ai_raw_output_{image_key}")
                
                for ext in ['.webp', '.jpg', '.jpeg', '.png']:
                    test_path = output_path + ext
                    try:
                        with open(test_path, 'wb') as f:
                            f.write(result)
                        
                        # Verify it's a valid image
                        with Image.open(test_path) as img:
                            img.verify()
                        
                        print(f"   ✅ Saved as {ext}")
                        return self._convert_ai_output_to_png(test_path, temp_dir, image_key)
                    except Exception:
                        continue
                
                print(f"   ❌ Could not save bytes as valid image")
            
            # ===== CASE 3: List/Tuple =====
            elif isinstance(result, (list, tuple)):
                print(f"   Result is {type(result).__name__} with {len(result)} items")
                
                for i, item in enumerate(result):
                    if isinstance(item, str):
                        print(f"   Item {i}: {item}")
                        if os.path.exists(item):
                            print(f"   ✅ Found valid file")
                            return self._convert_ai_output_to_png(item, temp_dir, image_key)
                        elif item.startswith(('http://', 'https://')):
                            downloaded_path = self._download_ai_result(item, temp_dir, image_key)
                            if downloaded_path:
                                return self._convert_ai_output_to_png(downloaded_path, temp_dir, image_key)
            
            return None
                
        except Exception as e:
            print(f"   ❌ Error handling AI result: {str(e)}")
            return None

    def _download_ai_result(self, url, temp_dir, image_key):
        """Download image from URL returned by AI model"""
        try:
            print(f"   ⬇️ Downloading from: {url}")
            
            import requests
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                # Determine file extension
                content_type = response.headers.get('content-type', '').lower()
                
                if 'webp' in content_type or '.webp' in url.lower():
                    ext = '.webp'
                elif 'jpeg' in content_type or 'jpg' in content_type or '.jpg' in url.lower():
                    ext = '.jpg'
                elif 'png' in content_type or '.png' in url.lower():
                    ext = '.png'
                else:
                    ext = '.jpg'
                
                download_path = os.path.join(temp_dir, f"ai_download_{image_key}{ext}")
                
                with open(download_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"   ✅ Downloaded: {download_path}")
                return download_path
            
            print(f"   ❌ Download failed: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"   ❌ Download error: {str(e)}")
            return None

    def _convert_ai_output_to_png(self, source_path, temp_dir, image_key):
        """Convert AI output to PNG format for consistency"""
        try:
            print(f"   🔄 Converting to PNG: {source_path}")
            
            with Image.open(source_path) as img:
                print(f"   Input image: {img.format}, {img.size}")
                
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                
                # Save as PNG
                png_path = os.path.join(temp_dir, f"ai_final_{image_key}.png")
                img.save(png_path, format='PNG', quality=95)
                
                print(f"   ✅ Converted to PNG: {png_path}")
                return png_path
                
        except Exception as e:
            print(f"   ❌ Conversion error: {str(e)}")
            
            # Fallback: copy file as-is
            try:
                ext = os.path.splitext(source_path)[1]
                fallback_path = os.path.join(temp_dir, f"ai_fallback_{image_key}{ext}")
                shutil.copy2(source_path, fallback_path)
                print(f"   ⚠️ Copied as-is: {fallback_path}")
                return fallback_path
            except Exception:
                return None

    # ==================== IMAGE UTILITIES ====================

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

    def convert_to_png_if_needed(self, source_path, dest_path):
        """Convert any image format to PNG for consistency"""
        try:
            with Image.open(source_path) as img:
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                img.save(dest_path, format='PNG')
                print(f"   Converted to PNG: {dest_path}")
        except Exception as e:
            print(f"❌ Error converting image: {str(e)}")
            with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
                dst.write(src.read())
            print(f"   Copied file as-is")

    # ==================== PDF IMAGE EXTRACTION ====================

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
                        continue
                
                pix = None
        
        doc.close()
        return images_info

    def replace_all_images(self, pdf_path, images_info, new_images_folder, output_pdf_path):
        """Replace all extracted images with new images from folder"""
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
                        print(f"  ✓ Replaced image on page {page_num + 1}")
                    except Exception as e:
                        print(f"  ❌ Failed to insert image {new_image_path}: {str(e)}")
                        page.draw_rect(bbox, color=(0.9, 0.9, 0.9), fill=(0.9, 0.9, 0.9), overlay=False)
            
            doc.save(output_pdf_path)
            doc.close()
            print(f"✅ PDF with replaced images saved: {output_pdf_path}")
        except Exception as e:
            print(f"❌ Error in replace_all_images: {str(e)}")
            raise

    

    # ==================== TEXT REPLACEMENT ====================

    def diagnose_pdf_text(self, pdf_path, search_text):
        """Diagnostic function to see what text exists in PDF"""
        print(f"\n{'='*70}")
        print(f"PDF TEXT DIAGNOSTIC")
        print(f"{'='*70}")
        
        try:
            doc = fitz.open(pdf_path)
            print(f"Total pages: {len(doc)}")
            print(f"Searching for: '{search_text}'")
            print(f"{'='*70}\n")
            
            total_chars = 0
            found_pages = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                total_chars += len(text)
                
                if search_text.lower() in text.lower():
                    found_pages.append(page_num + 1)
                    print(f"✅ Page {page_num + 1}: FOUND")
                    
                    lines = text.split('\n')
                    for i, line in enumerate(lines):
                        if search_text.lower() in line.lower():
                            print(f"   Line: '{line.strip()[:100]}'")
                            break
                    print()
            
            print(f"{'='*70}")
            print(f"Summary:")
            print(f"  Total text characters: {total_chars}")
            if found_pages:
                print(f"  ✅ Found on pages: {found_pages}")
            else:
                print(f"  ❌ NOT FOUND on any page")
            print(f"{'='*70}\n")
            
            doc.close()
            
        except Exception as e:
            print(f"❌ Diagnostic error: {str(e)}")

    def replace_character_name_preserve_format(self, pdf_path, old_name, new_name, temp_dir):
        """Replace character name while preserving exact formatting"""
        if not old_name or old_name.strip() == "":
            print("⚠️ No original character name specified, skipping text replacement")
            final_pdf_path = os.path.join(temp_dir, "final_customized.pdf")
            shutil.copy2(pdf_path, final_pdf_path)
            return final_pdf_path, 0
            
        output_path = os.path.join(temp_dir, "final_customized.pdf")
        
        print(f"Searching for: '{old_name}'")
        print(f"Replacing with: '{new_name}'")
        print()
        
        try:
            doc = fitz.open(pdf_path)
            total_replacements = 0
            pages_with_replacements = []
            
            search_variations = list(set([
                old_name,
                old_name.strip(),
                old_name.lower(),
                old_name.upper(),
                old_name.title(),
                old_name.capitalize()
            ]))
            
            print(f"Searching for {len(search_variations)} variations")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_replacements = 0
                
                for search_text in search_variations:
                    text_instances = page.search_for(search_text)
                    
                    if text_instances:
                        print(f"Page {page_num + 1}: Found {len(text_instances)} instance(s) of '{search_text}'")
                        
                        for rect in text_instances:
                            try:
                                text_props = self.extract_text_properties(page, rect)
                                
                                size = text_props['size']
                                if len(new_name) > len(search_text):
                                    ratio = len(search_text) / len(new_name)
                                    size = size * ratio * 1.00
                                
                                # Erase old text
                                erase_rect = fitz.Rect(
                                    rect.x0 - 2,
                                    rect.y0 - 2,
                                    rect.x1 + 2,
                                    rect.y1 + 2
                                )
                                page.draw_rect(erase_rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
                                
                                # Determine font based on properties
                                font_name = "helv"
                                font_lower = text_props.get('font', '').lower()
                                
                                if 'bold' in font_lower and 'italic' in font_lower:
                                    font_name = "hebo"  # Helvetica Bold Oblique
                                elif 'bold' in font_lower:
                                    font_name = "hebo"  # Helvetica Bold
                                elif 'italic' in font_lower or 'oblique' in font_lower:
                                    font_name = "heit"  # Helvetica Oblique
                                
                                baseline_y = rect.y0 + (rect.height * 0.78)
                                
                                # Insert new text WITHOUT fontfile parameter
                                page.insert_text(
                                    (rect.x0, baseline_y),
                                    new_name,
                                    fontsize=size,
                                    fontname=font_name,  # Use built-in font names only
                                    color=(0, 0, 0),
                                    overlay=True
                                )
                                
                                page_replacements += 1
                                total_replacements += 1
                                    
                            except Exception as e:
                                print(f"  ❌ Error replacing: {str(e)}")
                                continue
                
                if page_replacements > 0:
                    pages_with_replacements.append(page_num + 1)
            
            if total_replacements > 0:
                print(f"\n✅ SUCCESS: Replaced {total_replacements} instances")
                print(f"   Pages modified: {pages_with_replacements}\n")
                doc.save(output_path, garbage=4, deflate=True, clean=True)
            else:
                print(f"\n⚠️ NO REPLACEMENTS MADE\n")
                shutil.copy2(pdf_path, output_path)
            
            doc.close()
            return output_path, total_replacements
            
        except Exception as e:
            print(f"❌ Text replacement error: {str(e)}")
            import traceback
            traceback.print_exc()
            shutil.copy2(pdf_path, output_path)
            return output_path, 0

    def extract_text_properties(self, page, rect):
        """Extract font properties from text at given rectangle"""
        try:
            blocks = page.get_text("dict", clip=rect)
            
            properties = {
                'font': 'helv',
                'size': 12,
                'color': (0, 0, 0)
            }
            
            for block in blocks.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if span_rect.intersects(rect):
                                properties['font'] = span.get("font", "helv")
                                properties['size'] = span.get("size", 12)
                                properties['color'] = span.get("color", 0)
                                return properties
            
            return properties
            
        except Exception as e:
            return {'font': 'helv', 'size': 12, 'color': (0, 0, 0)}


# ==================== LIST CUSTOMIZATIONS ENDPOINT ====================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listCustomizedBooks(request):
    """
    List all customized books for the authenticated user
    GET /books/customizations/
    """
    try:
        # Filter by user
        customized_books = Customizations.objects.select_related(
            'book', 'user_id'
        ).filter(user_id=request.user).order_by('-created_at')
        
        serializer = CustomizationSerializer(
            customized_books, many=True, context={"request": request}
        )
        
        return Response({
            "success": True,
            "count": customized_books.count(),
            "customizations": serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== GET SINGLE CUSTOMIZATION ENDPOINT ====================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def getCustomization(request, pk):
    """
    Get a single customization by ID
    GET /books/customizations/<id>/
    """
    try:
        customization = get_object_or_404(
            Customizations.objects.select_related('book', 'user_id'),
            pk=pk,
            user_id=request.user
        )
        
        serializer = CustomizationSerializer(customization, context={"request": request})
        
        return Response({
            "success": True,
            "customization": serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_404_NOT_FOUND)


# ==================== DELETE CUSTOMIZATION ENDPOINT ====================

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def deleteCustomization(request, pk):
    """
    Delete a customization
    DELETE /books/customizations/<id>/
    """
    try:
        customization = get_object_or_404(
            Customizations,
            pk=pk,
            user_id=request.user
        )
        
        book_title = customization.book.title
        child_name = customization.child_name
        
        customization.delete()
        
        return Response({
            "success": True,
            "message": f"Customization for '{child_name}' of '{book_title}' deleted successfully"
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_404_NOT_FOUND)


# ==================== FILE SERVING ENDPOINTS ====================

class CustomBookFileView(APIView):
    """
    Serve customized book PDF files
    GET /books/customizations/<id>/file/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        customization = get_object_or_404(
            Customizations,
            pk=pk,
            user_id=request.user
        )
        
        if not customization.custom_book:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        file_stream = io.BytesIO(customization.custom_book)
        response = FileResponse(
            file_stream,
            content_type=customization.custom_book_type or "application/pdf"
        )
        
        filename = f"{customization.child_name}_{customization.book.title}.pdf"
        filename = filename.replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class CustomChildImageView(APIView):
    """
    Serve child images from customizations
    GET /books/customizations/<id>/child-image/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        customization = get_object_or_404(
            Customizations,
            pk=pk,
            user_id=request.user
        )
        
        if not customization.child_image:
            return Response(
                {"error": "Child image not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        file_stream = io.BytesIO(customization.child_image)
        response = FileResponse(
            file_stream,
            content_type=customization.child_image_type or "image/jpeg"
        )
        
        filename = f"{customization.child_name}_photo.jpg"
        filename = filename.replace(' ', '_')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response




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

    def initialize_gradio_client(self):
        """Initialize Gradio client with error handling"""
        try:
            print("🤖 Initializing Gradio Client...")
            # Remove timeout and serialize parameters - not supported in newer versions
            client = Client("shada-elewa/koko-land-demo")
            print("✅ Gradio Client initialized successfully")
            return client
        except Exception as e:
            print(f"❌ Failed to initialize Gradio Client: {str(e)}")
            print("💡 The Hugging Face space might be sleeping. Visit: https://huggingface.co/spaces/shada-elewa/koko-land-demo")
            return None

    def process_with_gradio_client_with_retry(self, book_image_path, child_image_path, temp_dir, image_key, client):
        """Process book image with child image using Gradio Client with retry logic"""
        try:
            print(f"  🤖 Processing {image_key} with Gradio Client...")
            
            # Prepare images for Gradio
            processed_book_image_path = self.process_book_image_for_gradio(
                book_image_path, temp_dir, image_key
            )
            if not processed_book_image_path or not os.path.exists(processed_book_image_path):
                print(f"  ❌ Processed book image not found for {image_key}")
                return None
            
            print(f"  🚀 Sending request to Gradio API...")
            
            try:
                result_queue = queue.Queue()
                
                def make_api_call():
                    try:
                        # Use handle_file() instead of file()
                        result = client.predict(
                            cartoon_img=handle_file(processed_book_image_path),
                            kid_img=handle_file(child_image_path),
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