from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

# Import views from courses app
from courses import views
from courses.views import (
    home, category_detail, course_detail, lesson_detail, search, 
    teacher_dashboard, upload_course, manage_curriculum, login_success, 
    add_lesson, register, course_detail_edit, edit_course, edit_lesson, 
    delete_lesson, student_dashboard, enroll_course, all_courses, 
    about_us, contact_us, edit_profile, change_password, admin_dashboard, 
    assign_teacher, live_classes, teacher_detail, reject_teacher, 
    approve_teacher, deactivate_teacher, all_inquiries_view, 
    all_instructors_view, reply_inquiry, resolve_inquiry, 
    resolved_inquiries_list, mark_lesson_complete, teacher_queries, 
    reply_query, submit_lesson_query, admin_communication_hub, 
    student_queries, all_platform_courses, teacher_my_courses_view,
    teacher_upload_course_sb, edit_profile_sb, update_lesson_progress,
    verify_payment, api_google_login, api_verify_email, api_register,
    api_login, api_resend_otp, verify_email_web, api_reset_password,
    reset_password_web, api_mark_all_notifications_read, toggle_course_status
)
from courses import api_views
from rest_framework.authtoken.views import obtain_auth_token

admin.site.site_header = "Shreeji GyanSetu Administration"
admin.site.site_title = "GyanSetu Admin Portal"
admin.site.index_title = "Welcome to Shreeji GyanSetu Management"

urlpatterns = [
    # New Authentication Endpoints
    path('api/login/', api_login, name='api_login'),
    path('api/register/', api_register, name='api_register'),
    path('api/verify-email/', api_verify_email, name='api_verify_email'),
    path('api/resend-otp/', api_resend_otp, name='api_resend_otp'),
    path('api/google-login/', api_google_login, name='api_google_login'),
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path("", home, name='home'),
    path('chained_filter/', include('smart_selects.urls')),
    path('category/<slug:slug>/', category_detail, name='category_detail'),
    path('course/<slug:slug>/', course_detail, name='course_detail'),
    path('course/<slug:course_slug>/lesson/<int:lesson_id>/', lesson_detail, name='lesson_detail'),
    path('search/', search, name='search'),
    
    # Dashboards
    path('dashboard/teacher/', teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', student_dashboard, name='student_dashboard'), # Standardized path
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login-success/', login_success, name='login_success'),
    path('register/', register, name='register'),
    path('register/verify/', verify_email_web, name='verify_email_web'),
    path('api/reset-password/', api_reset_password, name='api_reset_password'),
    path('verify-otp/', verify_email_web, name='verify_email_web'),
    path('reset-password/', reset_password_web, name='reset_password_web'),
    
    # Teacher Management
    path('dashboard/teacher/upload/', upload_course, name='upload_course'),
    path('course/<slug:course_slug>/manage-curriculum/', manage_curriculum, name='manage_curriculum'),
    path('module/<int:module_id>/add-lesson/', add_lesson, name='add_lesson'),
    path('course/<slug:slug>/manage/', course_detail_edit, name='course_detail_edit'),
    path('course/<slug:slug>/edit/', edit_course, name='edit_course'),
    path('lesson/<int:lesson_id>/edit/', edit_lesson, name='edit_lesson'),
    path('lesson/<int:lesson_id>/delete/', delete_lesson, name='delete_lesson'),
    path('dashboard/teacher/queries/', teacher_queries, name='teacher_queries'),
    path('dashboard/teacher/queries/<int:query_id>/reply/', reply_query, name='reply_query'),
    path('dashboard/teacher/my-courses/', teacher_my_courses_view, name='teacher_my_courses'),
    path('dashboard/teacher/create-course/', teacher_upload_course_sb, name='teacher_upload_course_sb'),
    path('course/<slug:slug>/toggle-status/', toggle_course_status, name='toggle_course_status'),

    # Student Actions
    path('course/<slug:slug>/enroll/', enroll_course, name='enroll_course'),
    path('lesson/<int:lesson_id>/query/', submit_lesson_query, name='submit_lesson_query'),
    path('my-queries/', student_queries, name='student_queries'),
    path('api/mark-all-notifications-read/', api_mark_all_notifications_read, name='api_mark_all_read'),
    
    # Public & General
    path('courses/', all_courses, name='all_courses'),
    path('about/', about_us, name='about_us'),
    path('contact/', contact_us, name='contact_us'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('password/change/', change_password, name='change_password'),
    path('live-classes/', live_classes, name='live_classes'),
    path('teacher/<str:username>/', teacher_detail, name='teacher_detail'),
    path('dashboard/profile/edit/', edit_profile_sb, name='edit_profile_sb'),
    path('lessons/<int:lesson_id>/update-progress/', update_lesson_progress, name='update_lesson_progress'),
    
    # Admin Console
    path('admin-console/courses/', all_platform_courses, name='all_platform_courses'),
    path('admin-console/instructors/', all_instructors_view, name='all_instructors'),
    path('admin-console/inquiries/', all_inquiries_view, name='all_inquiries'),
    path('admin-console/communication/', admin_communication_hub, name='admin_communication'),
    path('admin-console/inquiry/reply/<int:msg_id>/', reply_inquiry, name='reply_inquiry'),
    path('admin-console/resolved-inquiries/', resolved_inquiries_list, name='resolved_inquiries_list'),
    
    # Admin Actions
    path('assign-teacher/<int:course_id>/', assign_teacher, name='assign_teacher'),
    path('reject-teacher/<int:teacher_id>/', reject_teacher, name='reject_teacher'),
    path('approve-teacher/<int:teacher_id>/', approve_teacher, name='approve_teacher'),
    path('deactivate-teacher/<int:teacher_id>/', deactivate_teacher, name='deactivate_teacher'),
    path('resolve-inquiry/<int:msg_id>/', resolve_inquiry, name='resolve_inquiry'),

    # API Endpoints
    
    # path('api/login/', obtain_auth_token, name='api_token_auth'), # Returns a Token
    # path('api/register/', api_views.UserRegistrationView.as_view(), name='api_register'),
    path('api/home/', api_views.AppHomeView.as_view(), name='api_home'),

    path('api/courses/', api_views.CourseListView.as_view(), name='api_courses'),
    path('api/my-learning/', api_views.MyCoursesView.as_view(), name='api_my_learning'),
    path('api/profile/', api_views.UserProfileView.as_view(), name='api_profile'),
    path('api/enroll/', api_views.EnrollCourseView.as_view(), name='api_enroll'),
    path('api/change-password/', api_views.ChangePasswordView.as_view(), name='api_change_password'),
    path('api/lessons/<int:lesson_id>/complete/', mark_lesson_complete, name='mark_lesson_complete'),
    path('api/lessons/<int:lesson_id>/query/', api_views.SubmitLessonQueryView.as_view(), name='api_submit_query'),
    path('api/lessons/<int:lesson_id>/queries/list/', api_views.LessonQueryListView.as_view(), name='api_query_list'),
    path('api/notifications/', api_views.NotificationListView.as_view(), name='api_notifications'),
    path('api/notifications/<int:notification_id>/read/', api_views.mark_notification_read, name='mark_notification_read'),
    path('api/lessons/<int:lesson_id>/update-progress/', update_lesson_progress, name='api_update_progress'),
    path('api/profile/update-fcm/', api_views.UpdateFCMTokenView.as_view(), name='api_update_fcm'),

    path('admin-console/course/<slug:slug>/delete/', views.delete_course, name='delete_course'),

    path('api/', api_views.ApiRoot.as_view(), name='api_root'),
    path("create-upi-collect/", views.create_upi_collect),
    path('api/save-fcm-token/', views.save_fcm_token, name='save_fcm_token'),


    # Payment
    path('verify-payment/', verify_payment, name='verify_payment'),

    path('api/teacher/courses/', api_views.TeacherMyCoursesView.as_view(), name='teacher_courses'),
    # 🚀 API Endpoints section ke andar ye do naye routes add karein:
    path('api/teacher/queries/', api_views.TeacherQueryListView.as_view(), name='api_teacher_queries'),
    path('api/teacher/queries/<int:query_id>/reply/', api_views.TeacherReplyQueryAPIView.as_view(), name='api_teacher_reply_query'),
    # 🚀 Nayi API Add Course ke liye
    path('api/teacher/course/create/', api_views.TeacherCourseCreateAPIView.as_view(), name='api_teacher_course_create'),
    # API endpoints section ke andar:
    
    # Modules manage karne ke liye
    path('api/teacher/course/<int:course_id>/modules/', api_views.TeacherModuleAPIView.as_view(), name='api_teacher_modules'),
    
    # Lesson upload karne ke liye
    path('api/teacher/module/<int:module_id>/add-lesson/', api_views.TeacherLessonCreateAPIView.as_view(), name='api_teacher_add_lesson'),

    path('api/teacher/course/<int:course_id>/toggle-status/', api_views.TeacherToggleCourseStatusAPIView.as_view(), name='api_toggle_course_status'),
    path('api/teacher/course/<int:course_id>/delete/', api_views.TeacherDeleteCourseAPIView.as_view(), name='api_delete_course'),   
    path('api/teacher/course/<int:course_id>/update/', api_views.TeacherCourseUpdateAPIView.as_view(), name='api_update_course'),
    path('api/teacher/lesson/<int:lesson_id>/update/', api_views.TeacherLessonUpdateAPIView.as_view(), name='api_update_lesson'),
    path('api/teacher/lesson/<int:lesson_id>/delete/', api_views.TeacherLessonDeleteAPIView.as_view(), name='api_delete_lesson'),
    path('api/forgot-password/', api_views.ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('api/reset-password/', api_views.ResetPasswordView.as_view(), name='api_reset_password'),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])