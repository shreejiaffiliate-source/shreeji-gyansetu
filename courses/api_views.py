from datetime import timedelta
from django.utils import timezone
import random
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import generics, permissions, status, decorators
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.permissions import IsAuthenticated
# ✅ DRF ke serializers ko alag naam se import karein taaki confusion na ho
from rest_framework import serializers as drf_serializers 

# Puraane imports ke sath ise check karo ki 'Module' aapke models se import ho raha hai
from .models import Course, MasterCategory, Notification, Profile, Carousel, Lesson, LessonQuery, Module
# Yeh line verify karo:
from .serializers import CourseSerializer, CategorySerializer, ModuleSerializer, UserSerializer, SliderSerializer

from django.db import IntegrityError
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
import razorpay
from django.conf import settings
from django.db.models import Count
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.text import slugify
import uuid

User = get_user_model()

class ApiRoot(APIView):
    def get(self, request, format=None):
        return Response({
            # ✅ Yahan 'api_token_auth' ko badal kar 'api_login' kar do
            'login': reverse('api_login', request=request, format=format), 
            'register': reverse('api_register', request=request, format=format),
            'home': reverse('api_home', request=request, format=format),
            'courses': reverse('api_courses', request=request, format=format),
            'my-learning': reverse('api_my_learning', request=request, format=format),
            'profile': reverse('api_profile', request=request, format=format),
            'enroll': reverse('api_enroll', request=request, format=format),
        })

# 1. Home Screen Data (Categories + Popular Courses)
class AppHomeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        sliders = Carousel.objects.filter(is_active=True).order_by('order')
        categories = MasterCategory.objects.all().order_by('order')
        popular_courses = Course.objects.filter(is_active=True).annotate(
        num_students=Count('students')
    ).order_by('-num_students', '-id').distinct()[:5]
        
        # Create a basic response dictionary
        data = {
            "sliders": SliderSerializer(sliders, many=True, context={'request': request}).data,
            "categories": CategorySerializer(categories, many=True, context={'request': request}).data,
            "popular_courses": CourseSerializer(popular_courses, many=True, context={'request': request}).data,
            "user": None # Default for guests
        }

        # If user is logged in, attach their profile data
        if request.user.is_authenticated:
            data["user"] = UserSerializer(request.user, context={'request': request}).data
            
        return Response(data)

# 2. List All Courses / Search
class CourseListView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Start with all active courses
        queryset = Course.objects.filter(is_active=True)
        
        # Get the category_slug from the URL parameters
        category_slug = self.request.query_params.get('category_slug')
        
        if category_slug:
            # Filter by the slug of the master category
            queryset = queryset.filter(master_category__slug=category_slug)
            
        return queryset

    # Ensure context is passed for absolute video URLs
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

# 3. Student's Enrolled Courses
class MyCoursesView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        # Direct query on Course model is more efficient for progress calculation
        return Course.objects.filter(
            students=self.request.user,
            is_active=True
        ).distinct()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
    def patch(self, request, *args, **kwargs):
        print("========== PATCH DATA ==========")
        print(request.data)
        print(request.FILES)
        return super().patch(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        if not serializer.is_valid():
            print("========== SERIALIZER ERRORS ==========")
            print(serializer.errors)
            return Response(serializer.errors, status=400)

        self.perform_update(serializer)

        return Response(serializer.data)

    def perform_update(self, serializer):
        print("DATA:", self.request.data)
        print("FILES:", self.request.FILES)
        try:
            # 1. Save the basic user data (first_name, last_name, email)
            user = serializer.save()
            
            # 2. Extract profile data
            profile_data = self.request.data
            profile = user.profile
            
            # 3. Validation for empty fields (English messages)
            # Yahan hum user model ka first_name check kar rahe hain
            if not user.first_name or user.first_name.strip() == "":
                raise ValueError("First name cannot be empty.")

            # 4. Update Profile fields (Common for both)
            profile.phone_number = profile_data.get('profile.phone_number', profile.phone_number)
            profile.branch = profile_data.get('profile.branch', profile.branch)
            profile.college_name = profile_data.get('profile.college_name', profile.college_name)
            profile.enrollment_number = profile_data.get('profile.enrollment_number', profile.enrollment_number)
            profile.qualification = profile_data.get('profile.qualification', profile.qualification)
            
            # 🚀 NAYA CODE (TEACHER KE LIYE)
            # Student ki profile mein ye value nahi aayegi, toh ye block skip ho jayega (Student Safe hai)
            exp_val = profile_data.get('profile.experience_years')
            if exp_val is not None and str(exp_val).strip() != "":
                try:
                    profile.experience_years = int(exp_val)
                except ValueError:
                    pass # Agar galti se text aa gaya toh error nahi dega, bas ignore karega
            
            dob = profile_data.get('profile.date_of_birth')
            if dob and dob.strip():
                profile.date_of_birth = dob
            elif dob == "":
                profile.date_of_birth = None
                
            profile.bio = profile_data.get('profile.bio', profile.bio)
            
            if 'profile.photo' in self.request.FILES:
                profile.photo = self.request.FILES['profile.photo']
                
            profile.save()

        except IntegrityError:
            # ✅ drf_serializers use kiya hai taaki crash na ho
            raise drf_serializers.ValidationError({
                "enrollment_number": "This enrollment number is already in use. Please provide a unique one."
            })
        except ValueError as e:
            # ✅ Yahan bhi drf_serializers use kiya hai
            raise drf_serializers.ValidationError({"error": str(e)})
    
class UserRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data 

        print("REGISTER DATA:", data) 
        
        # ✅ Flutter fields se match karo
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        first_name = data.get('firstName', '') # Flutter sends firstName
        last_name = data.get('lastName', '')   # Flutter sends lastName
        user_type = data.get('userType', 'Student') # Flutter sends userType

        # ✅ Flutter ke userType ko model ke Role enum se match karein
        role_value = "TEACHER" if user_type == 'Teacher' else "STUDENT"

        if not username or not password:
            return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # ✅ Yahan create_user mein 'role' field add karein
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role_value  # <--- Ye nayi line add karni hai
            )

            # ✅ Profile setup (Safe way)
            profile, created = Profile.objects.get_or_create(user=user)
            profile.user_type = user_type

            if user_type == 'Teacher':
                profile.qualification = data.get('qualification', '')
                # Experience ko number mein convert karo, empty string crash kar sakti hai
                exp = data.get('experience', '0')
                profile.experience_years = int(exp) if exp and exp.isdigit() else 0
                profile.is_approved = False 
            else:
                profile.is_approved = True 
                
            profile.save()
            
            return Response({"message": "Registration successful"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class EnrollCourseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        course_id = request.data.get('course_id')
        try:
            course = Course.objects.get(id=course_id)
            if course.students.filter(id=request.user.id).exists():
                return Response({"message": "Already enrolled"}, status=status.HTTP_200_OK)
            
            course.students.add(request.user)
            return Response({"message": "Enrolled successfully"}, status=status.HTTP_201_CREATED)
            
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        user = request.user

        # 1. Check if old password is correct
        if not user.check_password(old_password):
            return Response({"error": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Set and save new password
        user.set_password(new_password)
        user.save()

        # 3. Keep the user logged in after password change
        update_session_auth_hash(request, user)
        
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
    
class SubmitLessonQueryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            question_text = request.data.get('question')
            
            if not question_text:
                return Response({"error": "Question text is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Create the query linked to the student and the lesson
            LessonQuery.objects.create(
                lesson=lesson,
                student=request.user,
                question=question_text
            )
            
            return Response({"message": "Query submitted successfully"}, status=status.HTTP_201_CREATED)
            
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class LessonQueryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        # Fetch queries for this specific lesson asked by the current student
        queries = LessonQuery.objects.filter(
            lesson_id=lesson_id, 
            student=request.user
        ).order_by('-created_at')
        
        data = [{
            "id": q.id,
            "question": q.question,
            "answer": q.answer,
            "is_resolved": q.is_resolved,
            "created_at": q.created_at.strftime("%d %b, %Y")
        } for q in queries]
        
        return Response(data)
    
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        data = [{
            "id": n.id,
            "message": n.message,
            "lesson_id": n.query.lesson.id,
            "course_title": n.query.lesson.course.title
        } for n in notifications]
        return Response(data)

@decorators.api_view(['POST']) # Add this decorator
@decorators.permission_classes([IsAuthenticated]) # Add this decorator    
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({"status": "success"})
    except Notification.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
    
class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request}) # CRITICAL for last_position
        return context
    
# Initialize Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class EnrollCourseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        course_id = request.data.get('course_id')
        payment_id = request.data.get('razorpay_payment_id') # New field from Flutter

        if not payment_id:
            return Response({"error": "Payment ID is required"}, status=400)

        try:
            # 1. Verify Payment with Razorpay
            payment_details = client.payment.fetch(payment_id)
            
            # Check if payment is authorized/captured and amount matches
            if payment_details['status'] not in ['authorized', 'captured']:
                return Response({"error": "Payment not verified"}, status=400)

            # 2. Proceed with Enrollment
            course = Course.objects.get(id=course_id)
            if course.students.filter(id=request.user.id).exists():
                return Response({"message": "Already enrolled"}, status=200)
            
            course.students.add(request.user)
            return Response({"message": "Enrolled successfully"}, status=201)
            
        except razorpay.errors.BadRequestError:
            return Response({"error": "Invalid Payment ID"}, status=400)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class UpdateFCMTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"error": "Token is required"}, status=400)
        
        # Update the user's profile with the new token
        profile = request.user.profile
        profile.fcm_token = fcm_token
        profile.save()
        
        return Response({"message": "FCM Token updated successfully"}, status=200)
    
class TeacherMyCoursesView(generics.ListAPIView):
    
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # ✅ FIX: is_active=True hata diya. Ab Teacher ko apne saare courses (Draft + Published) dikhenge
        return Course.objects.filter(
            teacher=self.request.user 
        ).order_by('-id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    
# 🚀 FILE KE END MEIN ADD KAREIN
from .serializers import TeacherLessonQuerySerializer
from .models import LessonQuery

class TeacherQueryListView(generics.ListAPIView):
    serializer_class = TeacherLessonQuerySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Sirf wahi queries nikalenge jahan course ka teacher current login user hai
        return LessonQuery.objects.filter(
            lesson__module__course__teacher=self.request.user
        ).order_by('-created_at')

class TeacherReplyQueryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, query_id):
        try:
            # Query dhoondhein aur check karein ki ye isi teacher ke liye hai ya nahi
            query = LessonQuery.objects.get(id=query_id, lesson__module__course__teacher=request.user)
            answer_text = request.data.get('answer')

            if not answer_text or answer_text.strip() == "":
                return Response({"error": "Answer text cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

            query.answer = answer_text
            query.is_resolved = True
            query.save()

            return Response({"message": "Reply submitted successfully", "is_resolved": True}, status=status.HTTP_200_OK)
        except LessonQuery.DoesNotExist:
            return Response({"error": "Query not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.text import slugify
import uuid

class TeacherCourseCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if request.user.profile.user_type != 'Teacher' or not request.user.profile.is_approved:
            return Response({"error": "Only approved teachers can create courses."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        title = data.get('title')
        description = data.get('description')
        price = data.get('price', 0)
        
        # 🚀 FIX: Discount price nikal rahe hain
        discount_price = data.get('discount_price')
        if discount_price == '' or discount_price == 'null':
            discount_price = None

        category_id = data.get('master_category_id') 
        thumbnail = request.FILES.get('thumbnail')
        level = data.get('level', 'Beginner')

        if not title or not category_id:
            return Response({"error": "Title and Category are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            category = MasterCategory.objects.get(id=category_id)
            base_slug = slugify(title)
            unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

            course = Course.objects.create(
                title=title,
                slug=unique_slug,
                description=description,
                price=price,
                discount_price=discount_price, # 🚀 FIX: Yahan Save Hoga
                level=level,
                master_category=category,      # 🚀 FIX: Category yahan attach ho rahi hai
                teacher=request.user,
                thumbnail=thumbnail,
                is_active=False
            )
            return Response({"message": "Course created successfully!", "course_id": course.id}, status=status.HTTP_201_CREATED)
            
        except MasterCategory.DoesNotExist:
            return Response({"error": "Invalid Category selected."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# 🚀 1. MODULE (Chapter) CREATE & LIST KARNE KI API
class TeacherModuleAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        # Teacher ko uske course ke modules dikhane ke liye
        try:
            course = Course.objects.get(id=course_id, teacher=request.user)
            modules = Module.objects.filter(course=course).order_by('order')
            # Assuming ModuleSerializer is already in serializers.py
            serializer = ModuleSerializer(modules, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Course.DoesNotExist:
            return Response({"error": "Course not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, course_id):
        # Naya Module Add karne ke liye
        try:
            course = Course.objects.get(id=course_id, teacher=request.user)
            title = request.data.get('title')
            order = request.data.get('order', 0)

            if not title:
                return Response({"error": "Module title is required"}, status=status.HTTP_400_BAD_REQUEST)

            module = Module.objects.create(
                course=course,
                master_category=course.master_category,
                title=title,
                order=order
            )
            return Response({"message": "Module created successfully", "module_id": module.id}, status=status.HTTP_201_CREATED)
        except Course.DoesNotExist:
            return Response({"error": "Course not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)


# 🚀 2. LESSON (Video + PDF) UPLOAD KARNE KI API
class TeacherLessonCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # Video/PDF upload karne ke liye

    def post(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__teacher=request.user)
            
            title = request.data.get('title')
            lesson_type = request.data.get('lesson_type', 'Video')
            video_url = request.data.get('video_url', '')
            resources = request.data.get('resources', '')
            
            # File Uploads
            content_file = request.FILES.get('content_file') # MP4 Video
            notes_file = request.FILES.get('notes_file')     # PDF Notes
            
            # Boolean Toggle
            is_preview = str(request.data.get('is_preview')).lower() == 'true'

            if not title:
                return Response({"error": "Lesson title is required"}, status=status.HTTP_400_BAD_REQUEST)

            lesson = Lesson.objects.create(
                module=module,
                course=module.course,
                title=title,
                lesson_type=lesson_type,
                video_url=video_url,
                content_file=content_file,
                notes_file=notes_file,
                resources=resources,
                is_preview=is_preview,
                lecturer_name=request.user.get_full_name() or request.user.username
            )
            return Response({"message": "Lesson uploaded successfully!", "lesson_id": lesson.id}, status=status.HTTP_201_CREATED)

        except Module.DoesNotExist:
            return Response({"error": "Module not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 🚀 PUBLISH / UNPUBLISH API
class TeacherToggleCourseStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, teacher=request.user)
            course.is_active = not course.is_active
            course.save()
            return Response({"message": "Status updated", "is_active": course.is_active}, status=status.HTTP_200_OK)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

# 🚀 DELETE COURSE API
class TeacherDeleteCourseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, teacher=request.user)
            course.delete()
            return Response({"message": "Course deleted successfully"}, status=status.HTTP_200_OK)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        
# 🚀 EDIT COURSE API
class TeacherCourseUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, teacher=request.user)

            course.title = request.data.get('title', course.title)
            course.description = request.data.get('description', course.description)
            course.price = request.data.get('price', course.price)
            course.level = request.data.get('level', course.level)

            # 🚀 FIX: Discount Price Update
            discount = request.data.get('discount_price')
            if discount is not None:
                if str(discount).strip() == '' or str(discount) == 'null':
                    course.discount_price = None
                else:
                    course.discount_price = discount

            # 🚀 FIX: Category Update
            category_id = request.data.get('master_category_id')
            if category_id:
                try:
                    course.master_category = MasterCategory.objects.get(id=category_id)
                except MasterCategory.DoesNotExist:
                    pass

            thumbnail = request.FILES.get('thumbnail')
            if thumbnail:
                course.thumbnail = thumbnail

            course.save()
            return Response({"message": "Course updated successfully!"}, status=status.HTTP_200_OK)

        except Course.DoesNotExist:
            return Response({"error": "Course not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)    

# 🚀 EDIT LESSON API
class TeacherLessonUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, lesson_id):
        try:
            # Check if lesson belongs to the teacher
            lesson = Lesson.objects.get(id=lesson_id, module__course__teacher=request.user)

            lesson.title = request.data.get('title', lesson.title)
            lesson.lesson_type = request.data.get('lesson_type', lesson.lesson_type)
            lesson.video_url = request.data.get('video_url', lesson.video_url)
            lesson.resources = request.data.get('resources', lesson.resources)
            
            is_preview = request.data.get('is_preview')
            if is_preview is not None:
                lesson.is_preview = str(is_preview).lower() == 'true'

            # Update files if new ones are provided
            if 'content_file' in request.FILES:
                lesson.content_file = request.FILES['content_file']
            if 'notes_file' in request.FILES:
                lesson.notes_file = request.FILES['notes_file']

            lesson.save()
            return Response({"message": "Lesson updated successfully!"}, status=status.HTTP_200_OK)

        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# 🚀 DELETE LESSON API
class TeacherLessonDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, lesson_id):
        try:
            # Check if lesson belongs to the teacher
            lesson = Lesson.objects.get(id=lesson_id, module__course__teacher=request.user)
            lesson.delete()
            return Response({"message": "Lesson deleted successfully!"}, status=status.HTTP_200_OK)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import traceback # Ise file ke top par add kar lena

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            email = request.data.get('email')
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(email=email).first()
            if not user:
                return Response({"error": "No user found with this email address."}, status=status.HTTP_404_NOT_FOUND)

            otp = str(random.randint(100000, 999999))
            
            # 🚀 ASLI FIX: Profile missing crash fix
            profile, created = Profile.objects.get_or_create(user=user)
            profile.email_verification_token = otp
            profile.token_created_at = timezone.now() 
            profile.save()

            try:
                subject = 'Password Reset OTP - Shreeji GyanSetu'
                message = f'Hello {user.first_name},\n\nYour OTP for password reset is: {otp}\n\nThis OTP is valid for 15 minutes.'
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
                return Response({"message": "OTP sent successfully to your email."}, status=status.HTTP_200_OK)
            except Exception as mail_error:
                # 🔥 DEV HACK
                print("==================================================")
                print(f"🚨 EMAIL NAHI GAYA! ERROR: {mail_error}")
                print(f"🔑 APP MEIN YE OTP DAAL DE: {otp}")
                print("==================================================")
                return Response({"message": "Email failed, but you can use terminal OTP."}, status=status.HTTP_200_OK)

        except Exception as main_error:
            print("🚨🚨🚨 FATAL CRASH IN FORGOT PASSWORD 🚨🚨🚨")
            traceback.print_exc()
            return Response({"error": "Server crashed. Check Django terminal."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 🚀 NAYI API: Reset Password (Naya password set karne ke liye)
class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('password')

        if not email or not otp or not new_password:
            return Response({"error": "Email, OTP and new password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            profile = user.profile

            # 1. Check if OTP matches
            if profile.email_verification_token != otp:
                return Response({"error": "Invalid OTP. Please try again."}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Check if OTP is expired (e.g., 15 minutes validity)
            if profile.token_created_at:
                expiry_time = profile.token_created_at + timedelta(minutes=15)
                if timezone.now() > expiry_time:
                    return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Set New Password
            user.set_password(new_password)
            user.save()

            # 4. Clear the OTP so it can't be used again
            profile.email_verification_token = None
            profile.save()

            return Response({"message": "Password reset successfully. You can now login."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)