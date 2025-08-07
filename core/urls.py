"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from portal import views as p
from django.conf import settings
from django.conf.urls.static import static
from portal.views import custom_admin_view
from django.contrib import admin


urlpatterns = [
    path("ops-a9d4b1/", admin.site.urls),   # 访问路径 /ops/，反向名用 admin:index
    path("admin/", custom_admin_view),
    path("", p.home, name="home"),
    #认证
    path("auth/register/", p.register_view, name="register"),
    path("auth/login/",    p.login_view,    name="login"),
    path("auth/logout/",   p.logout_view,   name="logout"),
    #家长
    path("parent/",  p.parent_dashboard,    name="parent"),
    path("premium/", p.premium_page,        name="premium"),
    path("parent/enroll/",             p.parent_enroll,       name="parent_enroll"),
    path("parent/enrollments/",        p.parent_enrollments,  name="parent_enrollments"),
    path("parent/enrollments/<int:enrollment_id>/cancel/", p.cancel_enrollment, name="cancel_enrollment"),
    #助教
    path("assistant/attendance/", p.assistant_attendance, name="assistant_attendance"),
    # 级联接口（助教+家长共用）
    path("assistant/api/slots/",      p.api_slots,      name="assistant_api_slots"),
    path("assistant/api/subgroups/",  p.api_subgroups,  name="assistant_api_subgroups"),
    # 助教表格/打勾
    path("assistant/attendance/table/", p.attendance_table, name="assistant_attendance_table"),
    path("assistant/attendance/mark/",  p.attendance_mark,  name="assistant_attendance_mark"),
    # 助教批量 & 导出
    path("assistant/attendance/mark_week_bulk/", p.attendance_mark_week_bulk, name="attendance_mark_week_bulk"),
    path("assistant/attendance/clear_week_bulk/", p.attendance_clear_week_bulk, name="attendance_clear_week_bulk"),
    path("assistant/attendance/export_csv/", p.attendance_export_csv, name="attendance_export_csv"),

    # 家长课程通知和课程资料
    path("parent/notices/",    p.parent_notices,    name="parent_notices"),
    path("parent/resources/",  p.parent_resources,  name="parent_resources"),
    path(
        "parent/subgroup/comment/",
        p.parent_comment_submit,
        name="parent_comment_submit",
    ),

    # 助教提交评论
    path(
        "assistant/subgroup/comment/",
        p.assistant_comment_submit,
        name="assistant_comment_submit",
    ),
    #助教以往评论
    path(
    "assistant/subgroup/comments/",
    p.assistant_comments_api,
    name="assistant_comments_api",
),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


