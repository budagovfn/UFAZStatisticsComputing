from .models import Coefficient, Student, workType


def total(student):
    result = 0

    for grade in student.grade_set.all():
        coef  = Coefficient.objects.get(
            subject = grade.subject,
            workType = grade.workType,
        )

        result += grade.value * coef.value

    return result / 20

def leaderboard():
    rows = [(i.UID, total(i)) for i in Student.objects.all()]
    rows.sort(key=lambda r: r[1], reverse = True)
    return rows

