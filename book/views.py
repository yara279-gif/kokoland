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
from gradio_client import Client, file

import fitz
import tempfile
import os
import io
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
from gradio_client import Client, file


class CustomizeBook(APIView):
    permission_classes = [IsAuthenticated]  # Add authentication
    
    def post(self, request, format=None):
        try:
            book_id = request.data.get('book')
            child_name = request.data.get('child_name')
            child_image = request.FILES.get('child_image')
            user_id = request.data.get('user_id')
            
            if not book_id or not child_name or not child_image or not user_id:
                return Response(
                    {"error": "book_id, child's name and child's image are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get book object
            book = Book.objects.get(id=book_id)
            book_path = book.book_file.path
            original_character_name = book.char_name
            
            print(f"\n{'='*70}")
            print(f"STARTING BOOK CUSTOMIZATION")
            print(f"{'='*70}")
            print(f"Book: {book.title}")
            print(f"Original Character: {original_character_name}")
            print(f"New Name: {child_name}")
            print(f"{'='*70}\n")
            
            # Read and validate child image
            child_image_data = self.process_child_image(child_image)
            if not child_image_data:
                return Response(
                    {"error": "Invalid child image format. Supported formats: JPEG, PNG, WebP, BMP, TIFF"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save child image to temporary file for Gradio Client
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_child:
                tmp_child.write(child_image_data)
                child_image_path = tmp_child.name

            # Create a temporary directory to store modified PDF
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract all images from PDF with their positions
                images_info = self.extract_images_with_positions(book_path, temp_dir)

                if not images_info:
                    return Response(
                        {"error": "No images found in the PDF"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Initialize Gradio Client
                try:
                    client = Client("shada-elewa/koko-land-demo")
                    print("✅ Gradio Client initialized successfully")
                except Exception as e:
                    print(f"❌ Failed to initialize Gradio Client: {str(e)}")
                    return Response(
                        {"error": "AI service initialization failed"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Process each image through AI model
                processed_images = {}
                for i, img_info in enumerate(images_info):
                    processed_image = self.process_with_gradio_client(
                        img_info['original_image_path'], 
                        child_image_path,
                        temp_dir,
                        img_info['image_key'],
                        client
                    )
                    if processed_image:
                        processed_images[img_info['image_key']] = processed_image
                        print(f"✅ Successfully processed image {img_info['image_key']}")
                    else:
                        print(f"❌ Failed to process image {img_info['image_key']}")

                # Clean up temporary child image
                if os.path.exists(child_image_path):
                    os.unlink(child_image_path)
                
                # Create a folder for processed images
                processed_images_folder = os.path.join(temp_dir, "processed_images")
                os.makedirs(processed_images_folder, exist_ok=True)
                
                # Copy processed images to the folder with sequential names
                processed_image_files = []
                for i, (image_key, image_path) in enumerate(processed_images.items()):
                    new_image_name = f"processed_{i:03d}.png"
                    new_image_path = os.path.join(processed_images_folder, new_image_name)
                    
                    # Copy the file with format conversion if needed
                    self.convert_to_png_if_needed(image_path, new_image_path)
                    processed_image_files.append(new_image_name)
                
                # Step 1: Replace images in PDF
                images_replaced_pdf = os.path.join(temp_dir, "images_replaced.pdf")
                self.replace_all_images(
                    book_path, 
                    images_info, 
                    processed_images_folder, 
                    images_replaced_pdf
                )
                
                # Check if PDF file exists and has content
                if not os.path.exists(images_replaced_pdf):
                    return Response(
                        {"error": "Generated PDF file not found"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                file_size = os.path.getsize(images_replaced_pdf)
                print(f"📄 PDF file size after image replacement: {file_size} bytes")
                
                if file_size == 0:
                    return Response(
                        {"error": "Generated PDF file is empty"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Step 2: Replace character names using PyMuPDF (FREE, no API needed)
                final_pdf_path, character_replacements = self.replace_character_name(
                    images_replaced_pdf,
                    original_character_name,
                    child_name,
                    temp_dir
                )
                
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
                
                print(f"\n{'='*70}")
                print(f"CUSTOMIZATION COMPLETE")
                print(f"{'='*70}")
                print(f"✅ Images processed: {len(processed_images)}/{len(images_info)}")
                print(f"✅ Text replacements: {character_replacements}")
                print(f"✅ Customization ID: {customization.id}")
                print(f"{'='*70}\n")
                
                return Response({
                    "message": "Book customized successfully!",
                    "child_name": child_name,
                    "images_processed": len(processed_images),
                    "total_images": len(images_info),
                    "character_replacements": character_replacements,
                    "character_replaced": character_replacements > 0,
                    "original_character_name": original_character_name,
                    "custom_book_url": customization.custom_book.url,
                    "customization_id": customization.id,
                    "book_title": book.title,
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

    def replace_character_name(self, images_replaced_pdf, original_character_name, child_name, temp_dir):
        """
        Replace character name in PDF using PyMuPDF (FREE, no API needed)
        """
        final_pdf_path = os.path.join(temp_dir, "final_customized.pdf")
        
        print(f"\n{'='*70}")
        print(f"TEXT REPLACEMENT - Using PyMuPDF")
        print(f"{'='*70}")
        print(f"Searching for: '{original_character_name}'")
        print(f"Replacing with: '{child_name}'")
        print(f"{'='*70}\n")
        
        # First, diagnose what text exists
        self.diagnose_pdf_text(images_replaced_pdf, original_character_name)
        
        # Try standard replacement
        print("🔧 Attempting standard text replacement...")
        result = self.replace_text_in_pdf(
            images_replaced_pdf,
            original_character_name,
            child_name,
            final_pdf_path
        )
        
        if result["success"] and result["replacements"] > 0:
            print(f"✅ Text replacement successful: {result['replacements']} replacements")
            return final_pdf_path, result["replacements"]
        
        # Try advanced method with redactions
        print("\n🔧 Attempting advanced redaction method...")
        result = self.advanced_text_replacement(
            images_replaced_pdf,
            original_character_name,
            child_name,
            final_pdf_path
        )
        
        if result["success"] and result["replacements"] > 0:
            print(f"✅ Advanced text replacement successful: {result['replacements']} replacements")
            return final_pdf_path, result["replacements"]
        
        # Fallback: copy original (images already replaced)
        print("\n⚠️ No text instances found - using PDF with replaced images only")
        import shutil
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
                    for line in lines[:2]:  # Show first 2 matches
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
                
                # Search for text instances
                text_instances = page.search_for(old_text)
                
                if text_instances:
                    print(f"   Found {len(text_instances)} instance(s) on page {page_num + 1}")
                    pages_modified.append(page_num + 1)
                    
                    for rect in text_instances:
                        # Get text properties
                        blocks = page.get_text("dict")["blocks"]
                        font_size = 12  # default
                        
                        # Find font size from text block
                        for block in blocks:
                            if block["type"] == 0:  # text block
                                for line in block["lines"]:
                                    for span in line["spans"]:
                                        span_rect = fitz.Rect(span["bbox"])
                                        if span_rect.intersects(rect):
                                            font_size = span["size"]
                                            break
                        
                        # Expand rectangle slightly
                        expanded_rect = rect + (-2, -2, 2, 2)
                        
                        # Cover old text with white rectangle
                        page.draw_rect(expanded_rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        # Adjust font size if new text is longer
                        if len(new_text) > len(old_text):
                            font_size = font_size * (len(old_text) / len(new_text))
                        
                        # Insert new text
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
            
            # Create variations to search for
            search_variations = list(set([
                old_text,
                old_text.strip(),
                old_text.lower(),
                old_text.upper(),
                old_text.title()
            ]))
            
            print(f"   Trying variations: {search_variations}")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                for search_text in search_variations:
                    areas = page.search_for(search_text)
                    
                    for area in areas:
                        # Add redaction with replacement text
                        page.add_redact_annot(
                            area, 
                            text=new_text, 
                            fontsize=11,
                            fill=(1, 1, 1),
                            text_color=(0, 0, 0)
                        )
                        total_replacements += 1
                
                # Apply redactions
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

    def process_with_gradio_client(self, book_image_path, child_image_path, temp_dir, image_key, client):
        """Process book image with child image using Gradio Client"""
        try:
            print(f"  🤖 Processing {image_key} with Gradio Client...")
            
            processed_book_image_path = self.process_book_image_for_gradio(book_image_path, temp_dir, image_key)
            if not processed_book_image_path:
                print(f"  ❌ Failed to process book image for {image_key}")
                return None
            
            print(f"  🚀 Sending request to Gradio Client...")
            try:
                result = client.predict(
                    cartoon_img=file(processed_book_image_path),
                    kid_img=file(child_image_path),
                    api_name="/run_app"
                )
                
                print(f"  📨 Gradio Client response received")
                
                if result:
                    processed_image_path = os.path.join(temp_dir, f"gradio_result_{image_key}")
                    
                    if isinstance(result, str) and os.path.exists(result):
                        source_path = result
                    elif isinstance(result, bytes):
                        source_path = os.path.join(temp_dir, f"raw_result_{image_key}.dat")
                        with open(source_path, 'wb') as f:
                            f.write(result)
                    else:
                        print(f"  ❌ Unexpected result type: {type(result)}")
                        return None
                    
                    try:
                        with Image.open(source_path) as img:
                            final_path = os.path.join(temp_dir, f"gradio_final_{image_key}.png")
                            img.save(final_path, format='PNG')
                            return final_path
                    except Exception as img_error:
                        print(f"  ❌ Cannot identify image file: {str(img_error)}")
                        return None
                else:
                    print(f"  ❌ No result from Gradio Client")
                    return None
                    
            except Exception as api_error:
                print(f"  ❌ Gradio Client API error: {str(api_error)}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error processing image {image_key}: {str(e)}")
            return None

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

    def process_child_image(self, child_image):
        """Process and validate child image, convert to appropriate format"""
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
            img.save(output_buffer, format='JPEG', quality=95)
            processed_data = output_buffer.getvalue()
            return processed_data
            
        except Exception as e:
            print(f"❌ Error processing child image: {str(e)}")
            return None

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

    def replace_all_images(self, pdf_path, images_info, new_images_folder, output_pdf_path):
        """Replaces all extracted images with new images from a folder."""
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
        print(f"✅ PDF with replaced images saved")
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





