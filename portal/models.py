from django.db import models
from django.conf import settings
from datetime import date, timedelta
from django.core.exceptions import ValidationError
User = settings.AUTH_USER_MODEL

# —— 基础维度 ——
class Campus(models.Model):
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True, default="")
    def __str__(self): return self.name

class Semester(models.Model):
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    start_date = models.DateField()              # Week1 起始周的周一
    week_count = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.name} @ {self.campus}"

class Course(models.Model):
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    intro = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    def __str__(self): return f"{self.title} @ {self.campus}"

class CourseSlot(models.Model):
    """
    课程在某学期的固定周几 + 时段
    weekday: 1=Mon ... 7=Sun
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField()  # 1..7
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ("course", "semester", "weekday", "start_time", "end_time")

    def __str__(self):
        return f"{self.course.title} S:{self.semester.name} W{self.weekday} {self.start_time}-{self.end_time}"

class SubGroup(models.Model):
    # 细分班级（例：4-5pm 7-10 basic）
    course_slot = models.ForeignKey(CourseSlot, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    def __str__(self): return f"{self.name} / {self.course_slot}"


# 学生
User = settings.AUTH_USER_MODEL

class Student(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="students")
    full_name = models.CharField(max_length=120)
    birth_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        # 同一家长下，(姓名 + 生日) 组合近似唯一；生日为空时不做强校验
        indexes = [models.Index(fields=["parent", "full_name"])]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return f"{self.full_name} ({self.parent})"

#报名enroll
class Enrollment(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="enrollments")  # ← 新增
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    semester = models.ForeignKey('Semester', on_delete=models.CASCADE)
    course_slot = models.ForeignKey('CourseSlot', on_delete=models.SET_NULL, null=True, blank=True)
    sub_group = models.ForeignKey('SubGroup', on_delete=models.SET_NULL, null=True, blank=True)

    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("APPROVED", "APPROVED"),
        ("REJECTED", "REJECTED"),
        ("CANCELLED", "CANCELLED"),
    ]
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    paid_status = models.CharField(max_length=16, choices=[("UNPAID","UNPAID"),("PAID","PAID")], default="UNPAID")
    created_at = models.DateTimeField(auto_now_add=True)
    def clean(self):
        super().clean()
        # —— 自动把 student.parent 写进 parent（报名视图或 admin 都适用）
        if self.student and self.parent_id != self.student.parent_id:
            self.parent = self.student.parent
        # —— 双保险：若传入的 parent 与 student.parent 冲突就报错
        if self.student and self.parent_id != self.student.parent_id:
            raise ValidationError({'parent': 'Parents must match their children。'})
    def __str__(self):
        who = self.student.full_name if self.student else self.parent
        slot = f" [{self.course_slot.start_time}-{self.course_slot.end_time}]" if self.course_slot else ""
        return f"Enroll#{self.id} {who} -> {self.course}{slot} ({self.status})"

# —— 出勤（周维度） ——
class Attendance(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    course_slot = models.ForeignKey(CourseSlot, on_delete=models.CASCADE)
    sub_group = models.ForeignKey(SubGroup, on_delete=models.SET_NULL, null=True, blank=True)
    week_no = models.PositiveSmallIntegerField()    # 1..week_count
    date = models.DateField()                       # 展示日期
    status = models.CharField(max_length=8, choices=[("PRESENT","PRESENT"),("ABSENT","ABSENT"),("LATE","LATE")], default="PRESENT")
    marked_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="marked_attendance")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("enrollment", "course_slot", "week_no", "sub_group")

    def __str__(self):
        return f"A#{self.id} E{self.enrollment_id} W{self.week_no} {self.status}"

# —— 工具函数：给定 week_no 和 slot.weekday 计算日期（周一起算） ——
def compute_date_for_week(semester_start: date, week_no: int, weekday_1_to_7: int) -> date:
    # semester_start 是 Week1 的周一
    return semester_start + timedelta(weeks=week_no - 1, days=weekday_1_to_7 - 1)

# --- 班级通知（老师公告） ---
class ClassNotice(models.Model):
    course_slot = models.ForeignKey(CourseSlot, on_delete=models.CASCADE, related_name="notices")
    sub_group   = models.ForeignKey(SubGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="notices")
    title       = models.CharField(max_length=200)
    content     = models.TextField(blank=True)  # 可写富文本后再替换为富文本编辑器
    is_pinned   = models.BooleanField(default=False)
    visible_to  = models.CharField(  # 预留是否只对付费可见
        max_length=10, choices=[("ALL", "All"), ("PAID", "Paid only")], default="ALL"
    )
    is_active   = models.BooleanField(default=True)
    order_no    = models.PositiveIntegerField(default=0)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_pinned","-order_no", "-created_at")

    def __str__(self):
        sg = f" / {self.sub_group.name}" if self.sub_group_id else ""
        return f"{self.title} ({self.course_slot}{sg})"


# --- 学习资料（视频/文件/图片），挂在 Sub group 上 ---
#def resource_upload_path(instance, filename):
#    # media/class_resources/<sub_group_id>/<filename>
#    return f"class_resources/{instance.sub_group_id}/{filename}"

#class LearningResource(models.Model):
#    sub_group   = models.ForeignKey(SubGroup, on_delete=models.CASCADE, related_name="resources")
#    title       = models.CharField(max_length=200)
#    description = models.TextField(blank=True)
    # 二选一或都填：支持外链视频（YouTube/Vimeo/阿里云点播）或直接上传 mp4/pdf/png…
#    video_url   = models.URLField(blank=True)
#    file        = models.FileField(upload_to=resource_upload_path, blank=True, null=True)
#    cover       = models.ImageField(upload_to=resource_upload_path, blank=True, null=True)

#    order_no    = models.PositiveIntegerField(default=0)
#    is_active   = models.BooleanField(default=True)
#    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
#    created_at  = models.DateTimeField(auto_now_add=True)
#    updated_at  = models.DateTimeField(auto_now=True)

 #   class Meta:
 #       ordering = ("order_no", "-created_at")

#    def __str__(self):
#        return f"{self.title} ({self.sub_group})"

# --- 学习资料（主表） ----------------------------------------------------------
class LearningResource(models.Model):
    sub_group   = models.ForeignKey(
        SubGroup, on_delete=models.CASCADE, related_name="resources")
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    order_no    = models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order_no", "-created_at")

    def __str__(self):
        return f"{self.title} ({self.sub_group})"


# --- 子表：具体的资源条目 ------------------------------------------------------
def lr_upload_path(instance, filename):
    # media/class_resources/<sub_group_id>/<filename>
    return f"class_resources/{instance.resource.sub_group_id}/{filename}"

resource_upload_path = lr_upload_path 

class LearningResourceItem(models.Model):
    class ResourceType(models.TextChoices):
        VIDEO = "VIDEO", "Video URL"
        FILE  = "FILE",  "Attachment"
        IMAGE = "IMAGE", "Image"
        LINK  = "LINK",  "External link"

    learning_resource = models.ForeignKey(
        LearningResource,
        on_delete=models.CASCADE,
        related_name="items",
    )
    type      = models.CharField(max_length=10, choices=ResourceType.choices)
    video_url = models.URLField(blank=True)
    file      = models.FileField(upload_to=resource_upload_path, blank=True, null=True)
    image     = models.ImageField(upload_to=resource_upload_path, blank=True, null=True)
    ext_url   = models.URLField(blank=True)
    order_no  = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order_no", "id")   # ← 默认按 order_no 排

    def __str__(self):
        return f"{self.get_type_display()} #{self.id} of {self.learning_resource}"




class Comment(models.Model):
    ROLE_CHOICES = [
        ("PARENT", "Parent"),
        ("ASSISTANT", "Assistant"),
    ]
    role        = models.CharField(max_length=10, choices=ROLE_CHOICES)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sub_group   = models.ForeignKey("portal.SubGroup", on_delete=models.CASCADE)
    # 只有家长的评论需要绑到他们孩子那次 Enrollment
    enrollment  = models.ForeignKey("portal.Enrollment", 
                                    null=True, blank=True,
                                    on_delete=models.CASCADE)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_role_display()} comment by {self.user} on {self.sub_group}"

    class Meta:
        ordering = ["-created_at"]


# Proxy models：让 admin 后台可以对两种评论分开管理
class ParentComment(Comment):
    class Meta:
        proxy = True
        verbose_name = "Parent Comment"
        verbose_name_plural = "Parent Comments"

class AssistantComment(Comment):
    class Meta:
        proxy = True
        verbose_name = "Assistant Comment"
        verbose_name_plural = "Assistant Comments"

