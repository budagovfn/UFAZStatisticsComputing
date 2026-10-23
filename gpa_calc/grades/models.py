from django.db import models

# Student class
class Student(models.Model):
    UID = models.CharField(max_length=20,unique=True)

    def __str__(self):
        return self.UID


# Subject

class Subject(models.Model):
    name = models.CharField(max_length=20, unique =True)

    def __str__(self):
        return self.name

# Work Type

class workType(models.Model):
    name = models.CharField(max_length=20, unique = True)

    def __str__(self):
        return self.name

# Coefficient

class Coefficient(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    workType = models.ForeignKey(workType, on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        unique_together = ('subject', 'workType')

    def __str__(self):
        return f"{self.workType}:{self.value},{self.subject}"

# Grade (out of 20)

class Grade(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    workType = models.ForeignKey(workType, on_delete=models.CASCADE)
    value = models.FloatField

    class Meta:
        unique_together = ('student', 'subject', 'workType')

    def __str__(self):
        return f"{self.student},{self.subject},{self.workType},{self.value}"