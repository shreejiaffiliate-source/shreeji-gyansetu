from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.text import slugify
from smart_selects.db_fields import ChainedForeignKey
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.conf import settings
from .utils import send_push_notification

class MasterCategory(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150,unique=True, blank=True)
    icon_class = models.CharField(max_length=50, default="fa-book")
    order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "1. Master Categories"
        ordering = ['order']
    def __str__(self): return self.title

class Course(models.Model):
    LEVEL_CHOICES = [('Beginner', 'Beginner'), ('Intermediate', 'Intermediate'), ('Advanced', 'Advanced')]
    master_category = models.ForeignKey(MasterCategory, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255,unique=True, blank=True)
    thumbnail = models.ImageField(upload_to='course_thumbnails/')
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Beginner')
    is_live = models.BooleanField(default=False)
    enrollment_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to=Q(profile__user_type= 'Teacher') | Q(profile__user_type= 'Admin'),
        related_name='taught_courses',
    )

    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='enrolled_courses',
        blank=True,
        limit_choices_to=Q(profile__user_type= 'Student')
    )

    @property
    def enrollment_count(self):
        """Returns the actual count from the ManyToMany relationship"""
        return self.students.count()

    def total_students(self):
        return self.students.count()

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_user_progress(self, user):
        """Returns progress as a decimal between 0.0 and 1.0"""
        if not user.is_authenticated:
            return 0.0
    
        # Use the correct related_name 'course_lessons' defined in Lesson model
        total_lessons = self.course_lessons.count()
    
    # FIX: You previously checked self.total_students == 0, which is wrong here.
    # We must check if the course actually has lessons.
        if total_lessons == 0:
            return 0.0
    
        # Count how many lessons of THIS course the user has completed
        completed_lessons = UserLessonProgress.objects.filter(
            user=user,
            lesson__course=self, # Look through the lesson to the course
            is_completed=True
        ).count()
    
        # Return rounded decimal for Flutter (e.g., 0.5)
        return round(completed_lessons / total_lessons, 2)




    class Meta:
        verbose_name_plural = "2. Courses"
    def __str__(self): return self.title

class Carousel(models.Model):
    title = models.CharField(max_length=150)
    image = models.ImageField(upload_to='carousels/')
    link = models.CharField(max_length=500, blank=True, help_text="Use relative link like /course/python-course/")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "0. Homepage Sliders"
        ordering = ['order']
    def __str__(self): return self.title

class Module(models.Model):
    # Changed related_name to 'category_modules' to avoid conflict with Course
    master_category = models.ForeignKey(MasterCategory, on_delete=models.SET_NULL, related_name='category_modules', null=True, blank=True)

    # Added related_name='modules' to fix AttributeError at /course/
    course = ChainedForeignKey(
        Course,
        chained_field="master_category",
        chained_model_field="master_category",
        show_all=False,
        auto_choose=True,
        sort=True,
        related_name='modules'
    )

    title = models.CharField(max_length=200) 
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "3. Modules" 
        ordering = ['order']

    def __str__(self): 
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    LESSON_TYPES = [('Video', 'Video'), ('PDF', 'Notes'), ('Quiz', 'Quiz')]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_lessons')
    
    # related_name='lessons' fixes AttributeError in course_detail
    module = ChainedForeignKey(
        Module,
        chained_field="course",
        chained_model_field="course",
        show_all=False,
        auto_choose=True,
        sort=True,
        related_name='lessons'
    )
    
    title = models.CharField(max_length=200)
    lesson_type = models.CharField(max_length=10, choices=LESSON_TYPES, default='Video')
    lecturer_name = models.CharField(max_length=100, blank=True, null=True, default="Admin")
    description = models.TextField(blank=True, null=True, help_text="Detailed information about this video content")
    thumbnail = models.ImageField(upload_to='lesson_thumbnails/', blank=True, null=True, help_text="Upload a specific thumbnail for this lesson video")
    video_url = models.URLField(blank=True, null=True, help_text="YouTube or Vimeo Link")
    content_file = models.FileField(
    upload_to='lessons/',
    blank=True,
    null=True,
    max_length=500
    )

    notes_file = models.FileField(
        upload_to='lesson_notes/',
        blank=True,
        null=True,
        max_length=500,
        help_text="Upload PDF Notes for this lesson"
    )    
    is_preview = models.BooleanField(default=False, help_text="Check if this is a free demo lesson")
    order = models.PositiveIntegerField(default=0)

    resources = models.TextField(
        blank=True, 
        null=True, 
        help_text="Add links or descriptions of resources here (e.g. GitHub link, useful websites)"
    )

    class Meta:
        verbose_name_plural = "4. Lessons"
        ordering = ['order']

    def __str__(self): 
        return f"{self.module.title} - {self.title}"
    
class UserLessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    last_position = models.FloatField(default=0.0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "4.1 Lesson Progress Tracking"
        # Prevents duplicate progress entries for the same user/lesson
        unique_together = ('user', 'lesson')

    def __str__(self):
        return f"{self.user.username} - {self.lesson.title} - Completed: {self.is_completed}"
    
# class LessonAssignment(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
#     is_completed = models.BooleanField(default=False)
#     completed_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ('user', 'lesson')

#     def __str__(self):
#         return f"{self.user.username} - {self.lesson.title}"

class StudyMaterial(models.Model):
    title = models.CharField(max_length=100)
    icon_class = models.CharField(max_length=50, default="fa-file-pdf")
    link = models.URLField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "5. Study Materials"
        ordering = ['order']
    def __str__(self): return self.title

class SuccessStory(models.Model):
    name = models.CharField(max_length=100)
    exam_name = models.CharField(max_length=100)
    rank = models.CharField(max_length=20)
    image = models.ImageField(upload_to='success_stories/')
    short_bio = models.TextField()

    class Meta:
        verbose_name_plural = "6. Success Stories"
    def __str__(self): return f"{self.name} ({self.rank})"

class YouTubeChannel(models.Model):
    name = models.CharField(max_length=100)
    subscribers = models.CharField(max_length=20)
    channel_url = models.URLField()

    class Meta:
        verbose_name_plural = "7. YouTube Channels"
    def __str__(self): return self.name

class Profile(models.Model):
    USER_TYPES = [
        ('Admin', 'Admin'),
        ('Teacher', 'Teacher'),
        ('Student', 'Student'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')

    # ✅ NAYE FIELDS FOR VERIFICATION & GOOGLE LOGIN
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    token_created_at = models.DateTimeField(null=True, blank=True)
    google_id = models.CharField(max_length=255, blank=True, null=True) # Google user identification
    auth_provider = models.CharField(max_length=50, default='email') # 'email' or 'google'

    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='Student')
    photo = models.ImageField(upload_to='profile_pics/', blank=True, null=True, default='default_user.png')
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    college_name = models.CharField(max_length=200, blank=True, null=True)
    branch = models.CharField(max_length=200, blank=True, null=True, help_text="e.g. Computer Science")
    fcm_token = models.TextField(blank=True, null=True)


    # Teacher Specific Information

    qualification = models.CharField(max_length=200, blank=True, null=True, help_text="e.g. M.Sc in Physics")
    subject_specialization = models.ForeignKey('MasterCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='teachers')
    experience_years = models.PositiveIntegerField(default=0,null=True, blank=True)
    bio = models.TextField(blank=True, help_text="Short professional summary")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    is_approved = models.BooleanField(default=False, help_text="Designates whether this teacher can upload courses.")
    is_rejected = models.BooleanField(default=False)

    # Student Specific Information
    enrollment_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.user_type} (Verified: {self.is_email_verified})"
    
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False, help_text="Check this once you have replied to the student")

    class Meta:
        verbose_name_plural = "8. Contact Messages"
        ordering = ['-created_at']

    def __str__(self): 
        return f"{self.name} - {self.subject}"




    class Meta:
        verbose_name_plural = "8. Contact Messages"

class LessonQuery(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='queries')

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='student_queries'
    )    
    question = models.TextField()
    answer = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "9. Lesson Queries"
        ordering = ['-created_at']

    def __str__(self): 
        return f"Query by {self.student.username} on {self.lesson.title}"
    

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_answer = None
        
        if not is_new:
            try:
                old_instance = LessonQuery.objects.only('answer').get(pk=self.pk)
                old_answer = old_instance.answer
            except LessonQuery.DoesNotExist:
                old_answer = None

        super().save(*args, **kwargs)

        # 1. NOTIFY TEACHER
        if is_new:
            teacher = self.lesson.course.teacher
            if teacher:
                from .models import Notification
                # Create notification and get the instance
                notif = Notification.objects.create(
                    user=teacher,
                    query=self,
                    message=f"New query from {self.student.username} in {self.lesson.title}"
                )

                if hasattr(teacher, 'profile') and teacher.profile.fcm_token:
                    send_push_notification(
                        fcm_token=teacher.profile.fcm_token,
                        title="New Student Question",
                        body=f"{self.student.username} asked a question in {self.lesson.title}",
                        lesson_id=self.lesson.id,
                        data={
                            "lesson_id": str(self.lesson.id), 
                            "type": "query",
                            "notification_id": str(notif.id) # ✅ ID bheji taaki teacher ke dashboard se badge hate
                        }
                    )

        # 2. NOTIFY STUDENT
        elif not old_answer and self.answer:
            from .models import Notification
            # Create notification and get the instance
            notif = Notification.objects.create(
                user=self.student,
                query=self,
                message=f"Your teacher replied to your query in {self.lesson.title}"
            )

            if hasattr(self.student, 'profile') and self.student.profile.fcm_token:
                send_push_notification(
                    fcm_token=self.student.profile.fcm_token,
                    title="Teacher Replied!",
                    body=f"Check the answer for your question in {self.lesson.title}",
                    lesson_id=self.lesson.id,
                    data={
                        "lesson_id": str(self.lesson.id), 
                        "type": "reply",
                        "notification_id": str(notif.id) # ✅ ID bheji taaki student ke icon se badge hate
                    }
                )
    
class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    query = models.ForeignKey(LessonQuery, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    
# Signals to automatically create a profile when a User is created

from django.contrib.auth import get_user_model
User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

    
class PendingRegistration(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    user_type = models.CharField(max_length=20, default='Student')
    qualification = models.CharField(max_length=255, blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)

    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email