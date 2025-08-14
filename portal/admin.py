from django.contrib import admin
from .models import Campus, Semester, Course, CourseSlot, SubGroup, Student, Enrollment, Attendance,ClassNotice, LearningResource,LearningResourceItem
from django import forms
from django.urls import reverse
from django.urls import path
from django.http import JsonResponse
from django.db.models import Q, F
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.admin import DateFieldListFilter
from django.http import HttpResponse
from django.utils import timezone
from django.templatetags.static import static
import csv
import calendar
from .models import ParentComment, AssistantComment
# —— 过滤：周次（1~10）——
class WeekNoListFilter(admin.SimpleListFilter):
    title = "Week"
    parameter_name = "week_no"

    def lookups(self, request, model_admin):
        # 如学期是 10 周，给 1~10；也可以写死 1~10
        return [(str(i), f"Week {i}") for i in range(1, 11)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(week_no=self.value())
        return queryset
    
@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("id","name","address")

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("id","name","campus","start_date","week_count","is_active")
    list_filter = ("campus","is_active")

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id","title","campus","is_active")
    list_filter = ("campus","is_active")

@admin.register(CourseSlot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("id","course","semester","weekday","start_time","end_time")
    list_filter = ("semester","course","weekday")
    # 关键：给自动补全提供可检索字段
    search_fields = (
        "course__title",            # 课程名
        "course__campus__name",     # 校区
        "semester__name",           # 学期名
    )
class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    fk_name = "sub_group"      # 用 Enrollment.sub_group 关联
    extra = 0                  # 不额外多显示空行
    readonly_fields = (
        "student",
        "course",
        "enrollment_course_slot",
        "status",
        "paid_status",
        "created_at",
    )
    can_delete = False         # 可根据需要允许删除

    # 如果想显示 course_slot 的可读文本，可以定义个方法
    def enrollment_course_slot(self, obj):
        slot = obj.course_slot
        if not slot:
            return "-"
        return f"{slot.get_weekday_display()} {slot.start_time:%H:%M}-{slot.end_time:%H:%M}"
    enrollment_course_slot.short_description = "时段"

@admin.register(SubGroup)
class SubGroupAdmin(admin.ModelAdmin):
    list_display = ("id","name","course_slot")
    list_filter = ("course_slot",)
    # 关键：给自动补全提供可检索字段
    search_fields = (
        "name",                                 # 子班名称
        "course_slot__course__title",           # 课程名
        "course_slot__semester__name",          # 学期名
        "course_slot__course__campus__name",    # 校区
    )
    inlines = [EnrollmentInline]
    def student_count(self, obj):
        return obj.enrollment_set.count()
    student_count.short_description = "人数"

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id","full_name","parent","birth_date","is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name","parent__username")

User = get_user_model()
# ========== 表单：初始过滤 ==========
class EnrollmentAdminForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # Admin.get_form 会把 request 注入；注意多拿一次 GET
        self.request: "HttpRequest|None" = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # 仅显示家长
        self.fields["parent"].queryset = User.objects.filter(role="PARENT", is_active=True)

        # ------- 关键：把 GET 里的初始值也算进去 -------
        data = self.data if self.is_bound else (self.request.GET if self.request else None)
        # -------------------------------------------

        # —— Student 依赖 Parent ——
        parent_id = data.get("parent") if data and data.get("parent") else getattr(self.instance, "parent_id", None)
        if parent_id:
            self.fields["student"].queryset = Student.objects.filter(parent_id=parent_id, is_active=True).order_by("full_name")
        else:
            self.fields["student"].queryset = Student.objects.none()

        # —— Semester 依赖 Course ——
        course_id = data.get("course") if data and data.get("course") else getattr(self.instance, "course_id", None)
        if course_id:
            self.fields["semester"].queryset = (
                Semester.objects.filter(courseslot__course_id=course_id)
                .distinct().order_by("-start_date")
            )
        else:
            self.fields["semester"].queryset = Semester.objects.none()

        # —— CourseSlot 依赖 Course + Semester ——
        sem_id = data.get("semester") if data and data.get("semester") else getattr(self.instance, "semester_id", None)
        if course_id and sem_id:
            self.fields["course_slot"].queryset = (
                CourseSlot.objects.filter(course_id=course_id, semester_id=sem_id)
                .order_by("weekday", "start_time")
            )
        else:
            self.fields["course_slot"].queryset = CourseSlot.objects.none()

        # —— SubGroup 依赖 CourseSlot ——
        slot_id = data.get("course_slot") if data and data.get("course_slot") else getattr(self.instance, "course_slot_id", None)
        if slot_id:
            self.fields["sub_group"].queryset = SubGroup.objects.filter(course_slot_id=slot_id)
        else:
            self.fields["sub_group"].queryset = SubGroup.objects.none()

    def clean(self):
        cleaned = super().clean()
        st, pa = cleaned.get("student"), cleaned.get("parent")
        if st and pa and st.parent_id != pa.id:
            cleaned["parent"] = st.parent       # 防止跨家长
        return cleaned


# ========== Admin ==========
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    form = EnrollmentAdminForm

    list_display = ("id", "student", "parent", "course", "semester", "course_slot", "sub_group",
                    "status", "paid_status", "created_at")
    list_filter  = ("semester", "course", "course_slot", "status", "paid_status")
    search_fields = ("student__full_name", "parent__username")

    # 关键：把 request 传给表单（便于初始过滤）
    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)
        class FormWithRequest(Form):
            def __init__(self2, *a, **kw):
                kw["request"] = request
                super().__init__(*a, **kw)
        return FormWithRequest

    # 保存前做一次 full_clean，触发表单/模型的校验与自动修正
    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    # ========== 提供 4 个联动接口 ==========
    def get_urls(self):
        urls = super().get_urls()
        my = [
            path("related/students/",   self.admin_site.admin_view(self.related_students),   name="enroll_related_students"),
            path("related/semesters/",  self.admin_site.admin_view(self.related_semesters),  name="enroll_related_semesters"),
            path("related/slots/",      self.admin_site.admin_view(self.related_slots),      name="enroll_related_slots"),
            path("related/subgroups/",  self.admin_site.admin_view(self.related_subgroups),  name="enroll_related_subgroups"),
        ]
        return my + urls

    def related_students(self, request):
        pid = request.GET.get("parent_id")
        qs = Student.objects.filter(parent_id=pid, is_active=True).order_by("full_name") if pid else Student.objects.none()
        data = [{"id": s.id, "text": s.full_name} for s in qs]
        return JsonResponse({"results": data})

    def related_semesters(self, request):
        cid = request.GET.get("course_id")
        qs = Semester.objects.filter(courseslot__course_id=cid).distinct().order_by("-start_date") if cid else Semester.objects.none()
        data = [{"id": s.id, "text": f"{s.name} @ {s.campus.name}"} for s in qs]
        return JsonResponse({"results": data})

    def related_slots(self, request):
        cid = request.GET.get("course_id")
        sid = request.GET.get("semester_id")
        qs = CourseSlot.objects.filter(course_id=cid, semester_id=sid).order_by("weekday", "start_time") if (cid and sid) else CourseSlot.objects.none()
        data = [{"id": x.id, "text": f"W{x.weekday} {x.start_time.strftime('%H:%M')}-{x.end_time.strftime('%H:%M')}"} for x in qs]
        return JsonResponse({"results": data})

    def related_subgroups(self, request):
        slot_id = request.GET.get("slot_id")
        qs = SubGroup.objects.filter(course_slot_id=slot_id) if slot_id else SubGroup.objects.none()
        data = [{"id": g.id, "text": g.name} for g in qs]
        return JsonResponse({"results": data})

    # 挂载联动 JS
    class Media:
        #js = ("portal/admin_enroll.js",)
        js = (static("portal/admin_enroll.js"),)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    """
    出勤列表（带搜索、筛选、导出）
    """
    list_display = (
        "id",
        "enrollment",         # 显示“Enroll#X 学生 -> 课程 …”
        "course_slot",        # 时段（课程+学期+起止时间）
        "sub_group",
        "week_no",
        "date",
        "status",
        "marked_by",
        "created_at",
    )
    list_select_related = (
        "enrollment", "enrollment__student", "enrollment__parent",
        "enrollment__course", "enrollment__course__campus",
        "course_slot", "course_slot__course", "course_slot__semester",
        "sub_group", "marked_by",
    )

    # —— 显示搜索框：可搜 校区/课程/学生/家长/子班/学期/时段 —— 
    search_fields = (
        "enrollment__student__full_name",
        "enrollment__parent__username",
        "enrollment__course__title",
        "enrollment__course__campus__name",
        "course_slot__course__title",
        "course_slot__semester__name",
        "sub_group__name",
        # 时间字段支持以字符串形式搜索，如 18:00 或 Tue
        "course_slot__start_time",
        "course_slot__end_time",
    )
    search_help_text = "支持：校区 / 课程 / 学生 / 家长 / 子班 / 学期 / 时段(如 18:00)"

    # —— 筛选器：校区/课程/学期/时段/子班/周次/日期/状态/标记人 —— 
    list_filter = (
        ("enrollment__course__campus", admin.RelatedOnlyFieldListFilter),
        ("enrollment__course", admin.RelatedOnlyFieldListFilter),
        ("course_slot__semester", admin.RelatedOnlyFieldListFilter),
        ("course_slot", admin.RelatedOnlyFieldListFilter),
        ("sub_group", admin.RelatedOnlyFieldListFilter),
        WeekNoListFilter,
        ("date", DateFieldListFilter),
        "status",
        ("marked_by", admin.RelatedOnlyFieldListFilter),
    )
    date_hierarchy = "date"

    # —— 顶部/底部都显示批量操作；支持“跨页全选”导出 —— 
    actions = ["export_selected_csv"]
    actions_on_top = True
    actions_on_bottom = True

    # —— 自定义列表模板，加“导出当前筛选”按钮 —— 
    change_list_template = "admin/portal/attendance/change_list.html"

    # ========== 导出（按钮：导出当前筛选） ==========
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "export/",
                self.admin_site.admin_view(self.export_filtered_csv),
                name="portal_attendance_export",
            ),
        ]
        return custom + urls
    # ---- 工具：将 weekday(1~7 或字符串) 转成英文星期缩写 ----
    def _weekday_label(self, slot):
        """返回 'Mon' / 'Tue' 等；如果不是数字就直接转字符串。"""
        w = getattr(slot, "weekday", None)
        if w is None:
            return ""
        try:
            i = int(w)              # 你的模型里 Mon=1 ~ Sun=7
            return calendar.day_abbr[(i - 1) % 7]  # 'Mon' 'Tue' ...
        except Exception:
            return str(w)

    def _slot_text(self, slot):
        """组合成 'Tue 18:00-19:00' 这样的时段字符串。"""
        if not slot:
            return ""
        wd = self._weekday_label(slot)
        start = slot.start_time.strftime("%H:%M") if slot.start_time else ""
        end   = slot.end_time.strftime("%H:%M") if slot.end_time else ""
        return f"{wd} {start}-{end}"
    
    def export_filtered_csv(self, request):
        """
        导出“当前筛选/搜索条件”的所有记录（无需选择）
        """
        # 用 Admin 的 ChangeList 拿到当前过滤后的 queryset
        cl = self.get_changelist_instance(request)
        qs = cl.get_queryset(request)

        filename = timezone.now().strftime("attendance_%Y%m%d_%H%M%S.csv")
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(resp)
        writer.writerow([
            "Campus", "Course", "Semester", "Time slot",
            "Sub group", "Student", "Parent",
            "Week", "Date", "Status", "Paid",
            "Marked by", "Created at",
        ])

        qs = qs.select_related(
            "enrollment", "enrollment__student", "enrollment__parent",
            "enrollment__course", "enrollment__course__campus",
            "course_slot", "course_slot__semester",
            "sub_group", "marked_by"
        ).order_by("date", "course_slot_id", "sub_group_id", "enrollment_id")

        for a in qs:
            campus = a.enrollment.course.campus.name if a.enrollment and a.enrollment.course else ""
            course = a.enrollment.course.title if a.enrollment and a.enrollment.course else ""
            semester = a.course_slot.semester.name if a.course_slot and a.course_slot.semester else ""
            # 时间段：周几 + 起止
            slot_txt = self._slot_text(a.course_slot)
            subgroup = a.sub_group.name if a.sub_group else ""

            student = a.enrollment.student.full_name if a.enrollment and a.enrollment.student else ""
            parent = a.enrollment.parent.username if a.enrollment and a.enrollment.parent else ""

            week = a.week_no
            date = a.date.strftime("%Y-%m-%d") if a.date else ""
            status = a.status
            paid = a.enrollment.paid_status if a.enrollment else ""

            marked_by = a.marked_by.username if a.marked_by else ""
            created = timezone.localtime(a.created_at).strftime("%Y-%m-%d %H:%M")

            writer.writerow([
                campus, course, semester, slot_txt,
                subgroup, student, parent,
                week, date, status, paid,
                marked_by, created
            ])
        return resp
     # ========== 批量操作：导出所选（支持跨页“选中全部 X 条”） ==========
    @admin.action(description="导出所选出勤为 CSV")
    def export_selected_csv(self, request, queryset):
        filename = timezone.now().strftime("attendance_selected_%Y%m%d_%H%M%S.csv")
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(resp)
        writer.writerow([
            "Campus", "Course", "Semester", "Time slot",
            "Sub group", "Student", "Parent",
            "Week", "Date", "Status", "Paid",
            "Marked by", "Created at",
        ])

        qs = queryset.select_related(
            "enrollment", "enrollment__student", "enrollment__parent",
            "enrollment__course", "enrollment__course__campus",
            "course_slot", "course_slot__semester",
            "sub_group", "marked_by"
        ).order_by("date", "course_slot_id", "sub_group_id", "enrollment_id")

        for a in qs:
            campus = a.enrollment.course.campus.name if a.enrollment and a.enrollment.course else ""
            course = a.enrollment.course.title if a.enrollment and a.enrollment.course else ""
            semester = a.course_slot.semester.name if a.course_slot and a.course_slot.semester else ""
            slot_txt = self._slot_text(a.course_slot)
            subgroup = a.sub_group.name if a.sub_group else ""
            student = a.enrollment.student.full_name if a.enrollment and a.enrollment.student else ""
            parent = a.enrollment.parent.username if a.enrollment and a.enrollment.parent else ""
            week = a.week_no
            date = a.date.strftime("%Y-%m-%d") if a.date else ""
            status = a.status
            paid = a.enrollment.paid_status if a.enrollment else ""
            marked_by = a.marked_by.username if a.marked_by else ""
            created = timezone.localtime(a.created_at).strftime("%Y-%m-%d %H:%M")
            writer.writerow([
                campus, course, semester, slot_txt,
                subgroup, student, parent,
                week, date, status, paid,
                marked_by, created
            ])
        return resp
# --- 修复：公告表单按 course_slot 过滤 sub_group，并做一致性校验 ---
from django import forms

class ClassNoticeAdminForm(forms.ModelForm):
    class Meta:
        model = ClassNotice
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 默认置空，避免跨时段误选
        self.fields["sub_group"].queryset = SubGroup.objects.none()

        # POST 提交：根据提交的 course_slot 过滤
        if self.is_bound:
            slot_id = self.data.get("course_slot") or self.data.get("course_slot_id")
            if slot_id:
                self.fields["sub_group"].queryset = SubGroup.objects.filter(course_slot_id=slot_id)

        # 编辑已有对象：根据实例的 course_slot 过滤
        elif self.instance and self.instance.pk and self.instance.course_slot_id:
            self.fields["sub_group"].queryset = SubGroup.objects.filter(
                course_slot_id=self.instance.course_slot_id
            )

    def clean(self):
        cleaned = super().clean()
        sub = cleaned.get("sub_group")
        slot = cleaned.get("course_slot")
        # 双保险：后端一致性校验，防止被绕过
        if sub and slot and sub.course_slot_id != slot.id:
            self.add_error("sub_group", "请选择该时段对应的小班（SubGroup）。")
        return cleaned
    
@admin.register(ClassNotice)
class ClassNoticeAdmin(admin.ModelAdmin):
    form = ClassNoticeAdminForm
    list_display  = ("id", "title", "course_slot", "sub_group",
                     "visible_to", "is_pinned", "created_by", "created_at")
    list_filter   = (("course_slot__semester", admin.RelatedOnlyFieldListFilter),
                     ("course_slot", admin.RelatedOnlyFieldListFilter),
                     ("sub_group", admin.RelatedOnlyFieldListFilter),
                     "visible_to", "is_pinned")
    search_fields = ("title", "content", "course_slot__course__title", "sub_group__name")
    autocomplete_fields = ("course_slot",)
    readonly_fields   = ("created_by",)
    ordering = ("-is_pinned", "-id")

    # 仅在“新增”页面，把 sub_group 初始清空，并打上 data-url
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["sub_group"].widget.attrs.update({
            "data-url": reverse("admin:portal_classnotice_subgroups_by_slot"),
        })
        return form

    # 子路由：按 slot_id 返回 JSON
    def get_urls(self):
        urls = super().get_urls()
        my = [
            path(
                "subgroups-by-slot/",
                self.admin_site.admin_view(self.subgroups_by_slot),
                name="portal_classnotice_subgroups_by_slot",
            )
        ]
        return my + urls

    def subgroups_by_slot(self, request):
        slot_id = request.GET.get("slot_id")
        data = []
        if slot_id:
            qs = SubGroup.objects.filter(course_slot_id=slot_id).order_by("name")
            data = [{"id": g.id, "label": str(g)} for g in qs]
        return JsonResponse({"results": data})

    class Media:
        js = ("portal/admin/filter_subgroups_by_slot.js",)


class LearningResourceItemInline(admin.TabularInline):
    """
    一个资源 (LearningResource) 可以挂多条 item：
    - 视频 (video_url)   - 文件 (file)
    - 图片 (image)       - 外链 (ext_url)
    """
    model  = LearningResourceItem
    extra  = 0                 # 默认不额外空行
    min_num = 1                # 至少一条
    fields = (
        "type",                # choice: VIDEO / FILE / IMAGE / LINK
        "video_url",
        "file",
        "image",
        "ext_url",
        "order_no",
    )
    readonly_fields = ()       # 这里也可以放预览图等

@admin.register(LearningResource)
class LearningResourceAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "title", "sub_group",
        "is_active", "created_by", "created_at",
    )
    list_filter   = (
        ("sub_group__course_slot__semester", admin.RelatedOnlyFieldListFilter),
        ("sub_group__course_slot", admin.RelatedOnlyFieldListFilter),
        ("sub_group", admin.RelatedOnlyFieldListFilter),
        "is_active",
    )
    search_fields = ("title", "description", "sub_group__name")
    autocomplete_fields = ("sub_group",)
    readonly_fields     = ("created_by",)
    fieldsets = (
        (None, {
            "fields": ("sub_group", "title", "description",
                       "order_no", "is_active")
        }),
    )
    inlines = [LearningResourceItemInline]

    # —— 你原来复制到其他小班的动作保持不动 ——
    actions = ["clone_to_other_subgroups"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# 用来给 Proxy model 加一个「按校区筛选」的 filter
class CampusFilter(admin.SimpleListFilter):
    title = "Campus"
    parameter_name = "campus"

    def lookups(self, request, model_admin):
        qs = model_admin.model.objects.all()
        campuses = set(q.sub_group.course_slot.course.campus for q in qs)
        return [(c.id, c.name) for c in campuses]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                sub_group__course_slot__course__campus_id=self.value()
            )
        return queryset

@admin.register(ParentComment)
class ParentCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "enrollment", "sub_group", "content", "created_at"
    )
    list_filter = (
        CampusFilter,
        "created_at",
    )
    search_fields = (
        "user__username",
        "enrollment__student__full_name",
        "sub_group__name",
        "content",
    )
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role="PARENT")


@admin.register(AssistantComment)
class AssistantCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "sub_group", "content", "created_at"
    )
    list_filter = (
        CampusFilter,
        "created_at",
    )
    search_fields = (
        "user__username",
        "sub_group__name",
        "content",
    )
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role="ASSISTANT")





    
