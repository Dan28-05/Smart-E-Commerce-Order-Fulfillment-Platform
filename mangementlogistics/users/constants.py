from django.db import models

class UserRole (models.TextChoices):
    ADMIN ="Admin" ,"Quan tri vien "
    DRIVER = "Driver","Tai xe"    
    CUSTOMER = "Customer","Khach hang"  
    