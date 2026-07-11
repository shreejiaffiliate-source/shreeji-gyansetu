from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import LessonQuery, MasterCategory, Course, Module, Lesson, Profile, Carousel, UserLessonProgress

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterCategory
        fields = ['id', 'title', 'slug', 'icon_class']

from rest_framework import validators # Ye import zaroori hai

from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):

    enrollment_number = serializers.CharField(
        required=True,
        error_messages={
            "blank": "Enrollment number cannot be empty.",
            "required": "Please provide your enrollment number."
        }
    )

    class Meta:
        model = Profile
        fields = [
            'user_type',
            'photo',
            'phone_number',
            'college_name',
            'branch',
            'enrollment_number',
            'qualification',
            'experience_years',
            'date_of_birth',
            'bio',
            'is_approved'
        ]

    def validate_enrollment_number(self, value):
        if self.instance:
            if Profile.objects.exclude(pk=self.instance.pk).filter(
                enrollment_number=value
            ).exists():
                raise serializers.ValidationError(
                    "This enrollment number is already registered. Please use a unique one."
                )
        else:
            if Profile.objects.filter(enrollment_number=value).exists():
                raise serializers.ValidationError(
                    "This enrollment number is already registered. Please use a unique one."
                )

        return value

class UserSerializer(serializers.ModelSerializer):

    profile = ProfileSerializer(read_only=True)
    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "profile",
            "profile_photo",
        ]

    def get_profile_photo(self, obj):
        request = self.context.get("request")

        if hasattr(obj, "profile") and obj.profile.photo:
            if request:
                return request.build_absolute_uri(obj.profile.photo.url)
            return obj.profile.photo.url

        return None

class LessonSerializer(serializers.ModelSerializer):
    # This is the key Flutter is looking for
    video_url = serializers.SerializerMethodField()
    notes_file = serializers.SerializerMethodField()
    is_preview = serializers.BooleanField(default=False)
    last_position = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    resources = serializers.CharField(required=False, allow_null=True, allow_blank=True)


    class Meta:
        model = Lesson
        # Include content_file if you need it, but video_url is what the player uses
        fields = ['id', 'title', 'lesson_type', 'video_url', 'content_file', 'is_preview', 'order', 'notes_file', 'last_position', 'resources', 'is_completed']

    def get_video_url(self, obj):
        # 1. Check if an actual file was uploaded to 'content_file'
        if obj.content_file:
            request = self.context.get('request')
            if request is not None:
                # Build http://192.168.x.x:8000/media/lessons/your_video.mp4
                return request.build_absolute_uri(obj.content_file.url)
            return obj.content_file.url
        
        # 2. If no file exists, return the external link (YouTube/Vimeo) if it exists
        # Note: Ensure 'video_url' is the name of the field in your actual Model
        return getattr(obj, 'video_url', None)

    def get_notes_file(self, obj):
        if obj.notes_file: # Matches the field name in your Lesson model
            request = self.context.get('request')
            if request is not None:
                # Returns http://127.0.0.1:8000/media/lesson_notes/file.pdf
                return request.build_absolute_uri(obj.notes_file.url)
            return obj.notes_file.url
        return None
    
    def get_last_position(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            # Look up the progress for this specific user and lesson
            progress = UserLessonProgress.objects.filter(user=user, lesson=obj).first()
            return progress.last_position if progress else 0.0
        return 0.0
    
    def get_is_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Check the progress table for the boolean
            progress = UserLessonProgress.objects.filter(user=request.user, lesson=obj).first()
            if progress:
                return progress.is_completed
        return False

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'lessons']

    def __init__(self, *args, **kwargs):
        super(ModuleSerializer, self).__init__(*args, **kwargs)
        context = kwargs.get('context')
        if context:
            self.fields['lessons'].context.update(context)

class CourseSerializer(serializers.ModelSerializer):
    is_enrolled = serializers.SerializerMethodField()
    master_category = CategorySerializer(read_only=True)
    teacher = UserSerializer(read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    enrollment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'thumbnail', 'description', 
            'price', 'discount_price', 'level', 'is_live',
            'is_active', # 👈 YAHAN 'is_active' KO ADD KARNA HAI
            'master_category', 'teacher', 'enrollment_count', 'modules', 'is_enrolled', 'progress',
        ]

    def __init__(self, *args, **kwargs):
        super(CourseSerializer, self).__init__(*args, **kwargs)
        context = kwargs.get('context')
        if context:
            self.fields['modules'].context.update(context)

    def get_is_enrolled(self, obj):
        request = self.context.get('request')

        if request and request.user.is_authenticated:
            return obj.students.filter(id=request.user.id).exists()
            
        return False
    
    def get_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            prog = obj.get_user_progress(request.user)
            print(f"DEBUG: Serializer calculating progress for {obj.title}: {prog}")
            return prog
        return 0.0
    
    def get_is_enrolled(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.students.filter(id=user.id).exists()
        return False

class SliderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carousel
        fields = ['id', 'title', 'image', 'link', 'order', 'is_active']


# 🚀 FILE KE SABSE NICHE YE NAYA SERIALIZER ADD KAREIN (WEBSITE UNTOUCHED RAHEGI)
class TeacherLessonQuerySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_name = serializers.CharField(source='lesson.module.course.title', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = LessonQuery
        fields = [
            'id', 'student_name', 'course_name', 'lesson_title', 
            'question', 'answer', 'is_resolved', 'created_at_formatted'
        ]

    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime("%d %b, %Y")