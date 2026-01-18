from django.db import models
from store.models import Product
from django.conf import settings
# Create your models here.

class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING_PAYMENT", "Pending Payment"),
            ("CONFIRMED", "Confirmed"),
            ("SHIPPED", "Shipped"),
            ("DELIVERED", "Delivered"),
            ("CANCELLED", "Cancelled"),
        ],
        default="PENDING_PAYMENT"
    )

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"
    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.title} X {self.quantity}"


class OrderTracking(models.Model):
    order = models.ForeignKey(Order, related_name="tracking_updates", on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order} - {self.status}"


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    razorpay_order_id = models.CharField(max_length=200)
    razorpay_payment_id = models.CharField(max_length=200, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=500, null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    status = models.CharField(max_length=20, choices=[
        ("CREATED", "CREATED"),
        ("SUCCESS", "SUCCESS"),
        ("FAILED", "FAILED"),
    ], default="CREATED")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.id} - {self.status}"