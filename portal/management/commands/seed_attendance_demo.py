from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portal.models import Campus, Semester, Course, CourseSlot, SubGroup, Enrollment,Student
from datetime import date, time

User = get_user_model()

class Command(BaseCommand):
    help = "Seed demo data for assistant attendance"

    def handle(self, *args, **kwargs):
        campus, _ = Campus.objects.get_or_create(name="Auburn", defaults={"address":"A St"})
        sem, _ = Semester.objects.get_or_create(campus=campus, name="Term 3", defaults={"start_date": date(2025,7,21), "week_count": 10})
        course, _ = Course.objects.get_or_create(campus=campus, title="Basketball Fundamentals")
        slot, _ = CourseSlot.objects.get_or_create(course=course, semester=sem, weekday=2, start_time=time(16,0), end_time=time(18,0))
        sg, _ = SubGroup.objects.get_or_create(course_slot=slot, name="7-10 basic")

        # users
        assist, _ = User.objects.get_or_create(username="assistant1", defaults={"role":"ASSISTANT"})
        assist.set_password("assistant123")
        assist.save()
        
        p1, _ = User.objects.update_or_create(username="parent1", defaults={"role":"PARENT"})
        p1.set_password("parent123")
        p1.save() 
        p2, _ = User.objects.update_or_create(username="parent2", defaults={"role":"PARENT"})
        p2.set_password("parent123")
        p2.save()
        # users（保持原样）...
    
    # 新增孩子
        s1, _ = Student.objects.get_or_create(parent=p1, full_name="Anna")
        s2, _ = Student.objects.get_or_create(parent=p2, full_name="Tom")

        Enrollment.objects.get_or_create(parent=p1, course=course, semester=sem, sub_group=sg, defaults={"status":"APPROVED","paid_status":"PAID"})
        Enrollment.objects.get_or_create(parent=p2, course=course, semester=sem, sub_group=sg, defaults={"status":"APPROVED","paid_status":"UNPAID"})
        Enrollment.objects.update_or_create(parent=p1, student=s1, course=course, semester=sem, sub_group=sg, defaults={"status":"APPROVED","paid_status":"PAID","course_slot":slot})
        Enrollment.objects.update_or_create(parent=p2, student=s2, course=course, semester=sem, sub_group=sg,defaults={"status":"APPROVED","paid_status":"UNPAID","course_slot":slot})


        self.stdout.write(self.style.SUCCESS("Seeded demo data. Login with assistant1 / assistant123"))
