# portal/views.py
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.db.models import Q
from django.conf import settings
import csv
from django.http import HttpResponse
from io import StringIO
import calendar
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import (
    Campus, Semester, Course, CourseSlot, SubGroup,Student,Comment,ParentComment,
    Enrollment, Attendance, compute_date_for_week,ClassNotice, LearningResource
)
from django.db.models import Q, Exists, OuterRef
from django.db import IntegrityError
from django.contrib.auth import login, get_user_model
from django.views.decorators.http import require_http_methods
from .forms import RegisterForm
from django.http import HttpResponseForbidden
from django.contrib.admin.sites import site as admin_site
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from .forms import CommentForm
from django.contrib import messages 
from django.views.decorators.http import require_http_methods

User = get_user_model()

# --------- 通用：角色校验装饰器 ---------
def role_required(*roles):
    """
    用法：@role_required("PARENT") 或 @role_required("ASSISTANT")
    """
    def _check(user):
        return user.is_authenticated and user.role in roles
    return user_passes_test(_check, login_url=reverse_lazy("login"))

# --------- 基础页面 ---------
def home(request):
    return render(request, "portal/home.html")

@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # 一定要写死 role
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email", ""),
                password=form.cleaned_data["password"],
                phone    = form.cleaned_data.get("phone") or "",
                role="PARENT",
                is_active=True,
                approval_status=User.Approval.PENDING,
            )
            messages.info(request,"Registration submitted. Please wait for admin approval.")
            return redirect("login")                  # go back to login page
    else:
        form = RegisterForm()

    return render(request, "portal/register.html", {"form": form})


User = get_user_model()

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if not user:
            return render(request, "portal/login.html",
                          {"error": "Invalid credentials"})
        # 超级管理员 → admin 后台
        if user.is_superuser:
            return redirect("/admin/")
        # ------------ 审批状态检查 ------------
        if user.approval_status == User.Approval.PENDING:
            messages.warning(request, "Waiting for approve.")
            return render(request, "portal/login.html")
        elif user.approval_status == User.Approval.REJECTED:
            messages.error(request, "Register rejected.")
            return render(request, "portal/login.html")

        # ------------ 已通过，正常登录 ------------
        login(request, user)

        # 1) URL 里带 ?next=/something/ 优先
        next_url = request.GET.get("next")
        if next_url:
            return redirect(next_url)
        
        # 2) 助教 → 助教考勤页
        if user.role == User.Role.ASSISTANT:
            return redirect(reverse("assistant_attendance"))

        # 3) 其他（家长等）→ 默认登录跳转
        return redirect(settings.LOGIN_REDIRECT_URL)

    # GET 请求直接渲染登录页
    return render(request, "portal/login.html")


def logout_view(request):
    logout(request)
    return redirect(reverse("home"))


#防止不是is staff登录后台
@staff_member_required
def custom_admin_view(request):
    return admin_site.index(request)

@login_required
@role_required("PARENT")
def parent_dashboard(request):
    # 1. 拿到该 parent 的所有 APPROVED enrollments，用于下拉
    enrolls = (
        Enrollment.objects
        .filter(parent=request.user, status="APPROVED")
        .select_related("student", "sub_group")
        .order_by("-created_at")
    )

    # 2. 准备一个空的提交表单
    form = CommentForm()

    # 3. 拿到这个 parent 已经提交过的所有评论
    comments = (
        Comment.objects
        .filter(user=request.user, role="PARENT")
        .select_related("sub_group", "enrollment__student")
        .order_by("-created_at")
    )

    return render(request, "portal/parent.html", {
        "enrolls": enrolls,
        "form": form,
        "comments": comments,
    })

@login_required
@role_required("PARENT")
@require_http_methods(["POST"])
def parent_comment_submit(request):
    subgroup_id = request.POST.get("subgroup_id")
    if not subgroup_id:
        messages.error(request, "必须选择一个小班。")
        return redirect("parent")

    try:
        sub = SubGroup.objects.get(pk=int(subgroup_id))
    except (ValueError, SubGroup.DoesNotExist):
        messages.error(request, "选择的小班无效。")
        return redirect("parent")

    # 取该家长在这个 sub_group 下最新一个 APPROVED 的 enrollment（可能为 None）
    enrollment = (
        Enrollment.objects
        .filter(parent=request.user, sub_group=sub, status="APPROVED")
        .order_by("-created_at")
        .first()
    )

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.role = "PARENT"
        comment.user = request.user
        comment.sub_group = sub
        comment.enrollment = enrollment
        comment.save()
        messages.success(request, "评论已提交。")
    else:
        # 拼一下错误信息，方便调试
        error_msgs = "; ".join(f"{field}: {','.join(errs)}" for field, errs in form.errors.items())
        messages.error(request, f"评论提交失败：{error_msgs}")

    return redirect("parent")


@login_required
@role_required("PARENT")
def premium_page(request):
    if not request.user.is_premium:
        return render(request, "portal/upgrade.html", status=402)
    return render(request, "portal/premium.html")

# --------- 助教出勤：页面 + 级联接口 ---------
@login_required
@role_required("ASSISTANT")
@ensure_csrf_cookie
def assistant_attendance(request):
    """
    出勤页面壳子：提供校区/学期/周几初始选项
    """
    campuses = Campus.objects.all().order_by("name")
    semesters = Semester.objects.filter(is_active=True).order_by("-start_date")
    weekdays = [(i, ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i-1]) for i in range(1, 8)]
    return render(request, "portal/assistant_attendance.html", {
        "campuses": campuses,
        "semesters": semesters,
        "weekdays": weekdays,
        "form": CommentForm(),
    })

# 顶部 import 已有，无需改

# ---- A) 放开级联接口权限：助教 + 家长 ----
@login_required
@role_required("ASSISTANT","PARENT")
def api_slots(request):
    campus_id = request.GET.get("campus_id")
    semester_id = request.GET.get("semester_id")
    weekday = request.GET.get("weekday")
    if not (campus_id and semester_id and weekday):
        return JsonResponse({"slots": []})
    qs = CourseSlot.objects.filter(
        semester_id=semester_id,
        weekday=int(weekday),
        course__campus_id=campus_id
    ).select_related("course")
    data = [{"id": s.id,
             "label": f"{s.course.title} {s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}"}
            for s in qs.order_by("start_time")]
    return JsonResponse({"slots": data})

@login_required
@role_required("ASSISTANT","PARENT")
def api_subgroups(request):
    slot_id = request.GET.get("slot_id")
    if not slot_id:
        return JsonResponse({"subgroups": []})
    qs = SubGroup.objects.filter(course_slot_id=slot_id).order_by("id")
    data = [{"id": g.id, "label": g.name} for g in qs]
    return JsonResponse({"subgroups": data})

# ---- B) 家长发起报名 ----

@login_required
@role_required("PARENT")
def parent_enroll(request):
    """
    GET: 渲染报名表（校区/学期/周几/时段/细分 + 选择孩子 或 新建孩子）
    POST: 创建 Enrollment(status=PENDING, paid_status=UNPAID, 绑定 course_slot & student)
    """
    if request.method == "POST":
        try:
            campus_id   = int(request.POST.get("campus_id"))
            semester_id = int(request.POST.get("semester_id"))
            weekday     = int(request.POST.get("weekday"))
            slot_id     = int(request.POST.get("slot_id"))
            subgroup_id = request.POST.get("subgroup_id")
            subgroup_id = int(subgroup_id) if subgroup_id else None
        except (TypeError, ValueError):
            ctx = _parent_enroll_ctx(request)
            ctx["error"] = "The parameters are incomplete, please select again"
            return render(request, "portal/parent_enroll.html", ctx)

        # 校验 slot
        try:
            slot = CourseSlot.objects.select_related("course","semester").get(
                id=slot_id, semester_id=semester_id, weekday=weekday, course__campus_id=campus_id
            )
        except CourseSlot.DoesNotExist:
            ctx = _parent_enroll_ctx(request)
            ctx["error"] = "Invalid time period, please select again"
            return render(request, "portal/parent_enroll.html", ctx)

        # 处理孩子：优先新建，否则选择
        new_student_name = (request.POST.get("new_student") or "").strip()
        student_id = request.POST.get("student_id")
        student = None
        if new_student_name:
            student = Student.objects.create(parent=request.user, full_name=new_student_name)
        else:
            if not student_id:
                ctx = _parent_enroll_ctx(request)
                ctx["error"] = "Please select a child or fill in the (Add a child's name)"
                return render(request, "portal/parent_enroll.html", ctx)
            try:
                student = Student.objects.get(id=int(student_id), parent=request.user, is_active=True)
            except Student.DoesNotExist:
                ctx = _parent_enroll_ctx(request)
                ctx["error"] = "Child selection is invalid"
                return render(request, "portal/parent_enroll.html", ctx)

        # 重复报名检查：同一学生+同一时段(+可选细分班) 不允许重复（排除已拒绝/已取消）
        exists = Enrollment.objects.filter(parent=request.user, student=student, course_slot=slot)
        if subgroup_id:
            exists = exists.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))
        if exists.exclude(status__in=["REJECTED","CANCELLED"]).exists():
            ctx = _parent_enroll_ctx(request)
            ctx["error"] = "This child has already submitted an application for this period. Please do not submit it again."
            return render(request, "portal/parent_enroll.html", ctx)

        Enrollment.objects.create(
            parent=request.user,
            student=student,
            course=slot.course,
            semester=slot.semester,
            course_slot=slot,
            sub_group_id=subgroup_id,
            status="PENDING",
            paid_status="UNPAID",
        )
        return redirect(reverse("parent_enrollments"))

    # GET
    return render(request, "portal/parent_enroll.html", _parent_enroll_ctx(request))

def _parent_enroll_ctx(request):
    campuses  = Campus.objects.all().order_by("name")
    semesters = Semester.objects.filter(is_active=True).order_by("-start_date")
    weekdays  = [(i, ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i-1]) for i in range(1,8)]
    students  = Student.objects.filter(parent=request.user, is_active=True).order_by("full_name")
    return {"campuses": campuses, "semesters": semesters, "weekdays": weekdays, "students": students}


@login_required
@role_required("PARENT")
def parent_enrollments(request):
    """
    我的报名列表
    """
    qs = (Enrollment.objects.filter(parent=request.user)
          .select_related("student","course","semester","course_slot","sub_group","course__campus")
          .order_by("-created_at"))
    return render(request, "portal/parent_enrollments.html", {"items": qs})

@login_required
@role_required("PARENT")
@require_http_methods(["POST"])
def cancel_enrollment(request, enrollment_id):
    """
    仅允许取消自己的 PENDING 报名
    """
    try:
        en = Enrollment.objects.get(id=enrollment_id, parent=request.user)
    except Enrollment.DoesNotExist:
        return redirect(reverse("parent_enrollments"))
    if en.status == "PENDING":
        en.status = "CANCELLED"
        en.save(update_fields=["status"])
    return redirect(reverse("parent_enrollments"))

# ---- C) 助教表：名单过滤优先使用 course_slot（兼容旧数据）----
@login_required
@role_required("ASSISTANT")
def attendance_table(request):
    try:
        campus_id   = int(request.GET.get("campus_id"))
        semester_id = int(request.GET.get("semester_id"))
        weekday     = int(request.GET.get("weekday"))
        slot_id     = int(request.GET.get("slot_id"))
        subgroup_id = request.GET.get("subgroup_id")
        subgroup_id = int(subgroup_id) if subgroup_id else None
    except (TypeError, ValueError):
        return HttpResponseBadRequest("missing or invalid params")

    try:
        slot = CourseSlot.objects.select_related("course","semester").get(
            id=slot_id, semester_id=semester_id, weekday=weekday, course__campus_id=campus_id
        )
    except CourseSlot.DoesNotExist:
        return HttpResponseBadRequest("invalid slot")

    sem  = slot.semester
    week_count = sem.week_count

    header = []
    for w in range(1, week_count + 1):
        d = compute_date_for_week(sem.start_date, w, slot.weekday)
        # 生成 "Tue 07/22"
        dow = calendar.day_abbr[d.weekday()]          # Mon/Tue/...
        header.append({"week": w, "date": f"{dow} {d.strftime('%m/%d')}"})


    # 优先筛选选中时段的报名；兼容旧数据（还未写入 course_slot 的）
    enrollments = (Enrollment.objects.filter(status="APPROVED")
                   .filter(Q(course_slot_id=slot.id) | (Q(course_slot__isnull=True) & Q(course_id=slot.course_id) & Q(semester_id=sem.id))))
    if subgroup_id:
        enrollments = enrollments.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))

    enrollments = enrollments.select_related("parent","sub_group").order_by("id")

    existing_qs = Attendance.objects.filter(course_slot=slot, week_no__lte=week_count)
    if subgroup_id:
        existing_qs = existing_qs.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))

    ex_map = {(a.enrollment_id, a.week_no, a.sub_group_id or 0): (a.status == "PRESENT") for a in existing_qs}

    rows = []
    for en in enrollments:
        row_subgroup_id = en.sub_group_id or (subgroup_id or None)
        cells = [{"week": h["week"], "present": ex_map.get((en.id, h["week"], row_subgroup_id or 0), False)} for h in header]
        rows.append({
            "enrollment_id": en.id,
            "student_name": en.student.full_name if en.student else en.parent.username,
            "parent_name": en.parent.username,
            "paid": (en.paid_status == "PAID"),
            "subgroup_name": en.sub_group.name if en.sub_group else "",
            "subgroup_id": row_subgroup_id or "",
            "slot_id": slot.id,
            "cells": cells,
        })

    html = render_to_string("portal/_attendance_table.html", {"slot": slot, "sem": sem, "header": header, "rows": rows}, request=request)
    return JsonResponse({"html": html})


@login_required
@role_required("ASSISTANT")
@require_http_methods(["POST"])
def attendance_mark(request):
    """
    打勾/取消勾：Upsert 到 Attendance
    JSON:
      {enrollment_id, course_slot_id, sub_group_id|null, week_no, present: true/false}
    """
    import json
    try:
        payload = json.loads(request.body.decode("utf-8"))
        enrollment_id = int(payload["enrollment_id"])
        slot_id       = int(payload["course_slot_id"])
        subgroup_id   = payload.get("sub_group_id")
        subgroup_id   = int(subgroup_id) if subgroup_id else None
        week_no       = int(payload["week_no"])
        present       = bool(payload["present"])
    except Exception:
        return HttpResponseBadRequest("invalid body")

    try:
        slot = CourseSlot.objects.select_related("semester").get(id=slot_id)
    except CourseSlot.DoesNotExist:
        return HttpResponseBadRequest("invalid slot")

    sem  = slot.semester
    d    = compute_date_for_week(sem.start_date, week_no, slot.weekday)

    obj, created = Attendance.objects.get_or_create(
        enrollment_id=enrollment_id,
        course_slot_id=slot_id,
        week_no=week_no,
        sub_group_id=subgroup_id,
        defaults={
            "date": d,
            "status": "PRESENT" if present else "ABSENT",
            "marked_by_id": request.user.id,
        },
    )
    if not created:
        obj.status = "PRESENT" if present else "ABSENT"
        obj.date = d
        obj.marked_by_id = request.user.id
        obj.save(update_fields=["status", "date", "marked_by_id"])

    return JsonResponse({"ok": True})
# --------- 批量：本周全员出勤 / 清空 ----------

@login_required
@role_required("ASSISTANT")
@require_http_methods(["POST"])
def attendance_mark_week_bulk(request):
    """
    POST JSON: {slot_id, subgroup_id|null, week_no}
    将该时段×细分班全部报名记录本周设为 PRESENT
    """
    return _bulk_update_week(request, present=True)

@login_required
@role_required("ASSISTANT")
@require_http_methods(["POST"])
def attendance_clear_week_bulk(request):
    """
    POST JSON: {slot_id, subgroup_id|null, week_no}
    将该周全部设为 ABSENT
    """
    return _bulk_update_week(request, present=False)

def _bulk_update_week(request, *, present: bool):
    import json
    try:
        payload = json.loads(request.body.decode("utf-8"))
        slot_id       = int(payload["slot_id"])
        week_no       = int(payload["week_no"])
        subgroup_id   = payload.get("subgroup_id")
        subgroup_id   = int(subgroup_id) if subgroup_id else None
    except Exception:
        return HttpResponseBadRequest("invalid body")

    slot = CourseSlot.objects.select_related("semester").get(id=slot_id)
    sem  = slot.semester
    date_obj = compute_date_for_week(sem.start_date, week_no, slot.weekday)

    # 找到需要更新的报名
    enrollments = Enrollment.objects.filter(status="APPROVED", course_slot_id=slot.id)
    if subgroup_id:
        enrollments = enrollments.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))

    count = 0
    for en in enrollments:
        obj, created = Attendance.objects.get_or_create(
            enrollment=en,
            course_slot_id=slot.id,
            week_no=week_no,
            sub_group_id=subgroup_id,
            defaults={
                "date": date_obj,
                "status": "PRESENT" if present else "ABSENT",
                "marked_by": request.user,
            }
        )
        if not created:
            obj.status = "PRESENT" if present else "ABSENT"
            obj.date = date_obj
            obj.marked_by = request.user
            obj.save(update_fields=["status","date","marked_by"])
        count += 1

    return JsonResponse({"ok": True, "updated": count})


# --------- 导出 CSV ----------
@login_required
@role_required("ASSISTANT")
def attendance_export_csv(request):
    """
    GET:
      slot_id (必需)
      subgroup_id (可空)
      strict=1/0        # 严格导出：无记录 => ABSENT；默认 1
      future_blank=0/1  # 将“未来周”保留为空（不标记 ABSENT），默认 0=也标记为 ABSENT
    说明：
      - 兼容旧数据：course_slot 为空但 course/semester 匹配的报名也导出
      - 严格模式下，所有空格会被写成 ABSENT（除非 future_blank=1 且该周在未来）
    """
    from datetime import date

    try:
        slot_id = int(request.GET.get("slot_id"))
        subgroup_id = request.GET.get("subgroup_id")
        subgroup_id = int(subgroup_id) if subgroup_id else None
        strict = bool(int(request.GET.get("strict", "1")))            # 默认严格
        future_blank = bool(int(request.GET.get("future_blank", "0"))) # 默认未来周也记为 ABSENT
    except (TypeError, ValueError):
        return HttpResponseBadRequest("missing params")

    slot = CourseSlot.objects.select_related("course","semester").get(id=slot_id)
    sem  = slot.semester
    week_count = sem.week_count
    today = date.today()

    def is_future_week(w:int)->bool:
        d = compute_date_for_week(sem.start_date, w, slot.weekday)
        return d > today

    # —— 与签到表一致：兼容旧报名
    enrollments = (
        Enrollment.objects.filter(status="APPROVED")
        .filter(
            Q(course_slot_id=slot.id) |
            (Q(course_slot__isnull=True) & Q(course_id=slot.course_id) & Q(semester_id=sem.id))
        )
        .select_related("student","parent","sub_group")
        .order_by("id")
    )
    if subgroup_id:
        enrollments = enrollments.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))

    # 出勤记录
    atts = Attendance.objects.filter(course_slot=slot)
    if subgroup_id:
        atts = atts.filter(Q(sub_group_id=subgroup_id) | Q(sub_group_id__isnull=True))
    att_map = {(a.enrollment_id, a.week_no): a.status for a in atts}

    # 写 CSV
    buf = StringIO()
    w = csv.writer(buf)
    #w.writerow(["Student", "Parent", "Paid"] + [f"W{wk}" for wk in range(1, week_count+1)])
    # 添加表头（含日期）
    header = ["Student", "Parent", "Paid"]
    for wk in range(1, week_count+1):
        d = compute_date_for_week(sem.start_date, wk, slot.weekday)
        dow = calendar.day_abbr[d.weekday()]
        date_str = d.strftime("%m/%d")
        header.append(f"W{wk} ({dow} {date_str})")
    w.writerow(header)

    for en in enrollments:
        student_name = en.student.full_name if en.student else en.parent.username
        row = [student_name, en.parent.username, en.paid_status]

        for wk in range(1, week_count+1):
            status = att_map.get((en.id, wk))  # "PRESENT"/"ABSENT"/None
            if status is None:
                #if strict:
                    # 未来周是否保留空白由 future_blank 控制
                  #  if future_blank and is_future_week(wk):
                   #     status = ""
                    #else:
                     #   status = "ABSENT"
                #else:
                    status = "ABSENT"
            row.append(status)
        w.writerow(row)

    filename = f"{slot.course.title}_{sem.name}_Week.csv".replace(" ", "_")
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8-sig")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
# ---- 家长端：课程通知 ----
@login_required(login_url="/portal/auth/login/")
@role_required("PARENT")
def parent_notices(request):
    parent = request.user

    # 该家长的报名（只看 APPROVED）
    enroll_qs = (Enrollment.objects
                 .filter(parent=parent, status="APPROVED")
                 .select_related("course_slot", "sub_group"))

    course_slot_ids = {e.course_slot_id for e in enroll_qs if e.course_slot_id}
    subgroup_ids     = {e.sub_group_id  for e in enroll_qs if e.sub_group_id}

    # 如果家长一个课都没报，直接空
    if not course_slot_ids:
        return render(request, "portal/parent_notices.html", {"items": []})

    # “付费可见”匹配（按相同 course_slot，且子班相同或 notice 不限定子班）
    paid_enrolls = (Enrollment.objects
        .filter(parent=parent, status="APPROVED", paid_status="PAID",
                course_slot_id=OuterRef("course_slot_id"))
        .filter(Q(sub_group__isnull=True) | Q(sub_group_id=OuterRef("sub_group_id")))
    )

    # 兼容 visible_to 的多种存储（ALL/PAID_ONLY/空）
    V_ALL  = ["ALL", "all", "", None]
    V_PAID = ["PAID_ONLY", "PAID", "paid_only"]

    qs = (ClassNotice.objects
          # 先限定在家长报名过的课时段
          .filter(course_slot_id__in=course_slot_ids)
          # 如果公告限定了子班，则必须命中家长孩子的子班；未限定子班（null）则表示整个时段都可见
          .filter(Q(sub_group__isnull=True) | Q(sub_group_id__in=subgroup_ids))
          # 付费限制
          .annotate(paid_match=Exists(paid_enrolls))
          .filter(Q(visible_to__in=V_ALL) | Q(visible_to__in=V_PAID, paid_match=True))
          .select_related("course_slot", "course_slot__course",
                          "course_slot__semester", "sub_group")
          .order_by("-is_pinned", "-created_at")
    )

    return render(request, "portal/parent_notices.html", {"items": qs})


# ---- 家长端：学习资料 ----
@login_required(login_url="/portal/auth/login/")
@role_required("PARENT")
def parent_resources(request):
    parent = request.user
    enrolls = Enrollment.objects.filter(parent=parent, status="APPROVED")
    subgroup_ids = {e.sub_group_id for e in enrolls if e.sub_group_id}

    qs = (LearningResource.objects
        .filter(is_active=True, sub_group_id__in=subgroup_ids)
        .select_related("sub_group", "sub_group__course_slot",
                        "sub_group__course_slot__course",
                        "sub_group__course_slot__semester")
        .prefetch_related("items")          # <-- 新增
        .order_by("order_no", "-created_at"))


    return render(request, "portal/parent_resources.html", {"items": qs})

@login_required
@role_required("ASSISTANT")
@require_http_methods(["POST"])
def assistant_comment_submit(request):
    subgroup_id = request.POST.get("subgroup_id") or request.POST.get("sub_group")
    if not subgroup_id:
        messages.error(request, "缺少细分班 ID。")
        return redirect("assistant_attendance")

    sub = get_object_or_404(SubGroup, pk=subgroup_id)

    form = CommentForm(request.POST)
    if form.is_valid():
        Comment.objects.create(
            role="ASSISTANT",
            user=request.user,
            sub_group=sub,
            content=form.cleaned_data["content"],
        )
        messages.success(request, "评论已提交。")
    else:
        error_msgs = "; ".join(f"{field}: {','.join(errs)}" for field, errs in form.errors.items())
        messages.error(request, f"评论提交失败：{error_msgs}")

    return redirect("assistant_attendance")



@login_required
@role_required("ASSISTANT")
def assistant_comments_api(request):
    subgroup_id = request.GET.get("subgroup_id")
    if not subgroup_id:
        return JsonResponse({"comments": []})
    comments = (
        Comment.objects
        .filter(role="ASSISTANT", sub_group_id=subgroup_id)
        .select_related("user")
        .order_by("-created_at")
    )
    data = [
        {
            "content": c.content,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
            "author": c.user.get_full_name() or c.user.username,
        }
        for c in comments
    ]
    return JsonResponse({"comments": data})

