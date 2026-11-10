from django.db import models


class Expense(models.Model):
    class Category(models.TextChoices):
        FOOD = 'Food', 'Food'
        TRANSPORT = 'Transport', 'Transport'
        BILLS = 'Bills', 'Bills'
        SHOPPING = 'Shopping', 'Shopping'
        OTHER = 'Other', 'Other'

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.category}: ${self.amount} - {self.description}"
