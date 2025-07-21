from django.db import models


class Complaint(models.Model):
    APPLICATION_TYPES = [
        ('complaint', 'Complaint'),
        ('grievance', 'Grievance'),
    ]

    METHODS = [
        ('seller', 'Seller'),
        ('buyer', 'Buyer'),
        ('affiliate', 'Affiliate'),
        ('anonymous', 'Anonymous'),
    ]

    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('complete', 'Complete'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
    ]

    full_name = models.CharField(max_length=255)
    last_names = models.CharField(max_length=255)
    identification = models.CharField(max_length=50)
    telephone = models.CharField(max_length=20)
    email = models.EmailField()
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    complaint = models.TextField()
    selected_application = models.CharField(max_length=10, choices=APPLICATION_TYPES)
    selected_method = models.CharField(max_length=10, choices=METHODS)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.full_name} - {self.selected_application}'
