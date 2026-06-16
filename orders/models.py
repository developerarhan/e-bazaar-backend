from django.db import models
from store.models import Product
from django.conf import settings
# Create your models here.

class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='orders',
    )
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
        default="PENDING_PAYMENT",
        db_index=True
    )
    shipping_name = models.CharField(max_length=100, blank=True)
    shipping_phone = models.CharField(max_length=15, blank=True)
    shipping_address = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_pincode = models.CharField(max_length=10, blank=True)



    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # for sorting

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Composite index
            models.Index(fields=['user', 'status'], name='order_user_status_idx'),
        ]

    @property
    def shipping_address_full(self):
        """
        Returns a single formatted string for display/invoice use.
        Returns empty string if no shipping info was saved
        (e.g. very old orders created before this field existed).
        """
        if not self.shipping_address:
            return ""
        
        parts = [self.shipping_address]
        if self.shipping_city:
            parts.append(self.shipping_city)
        if self.shipping_state:
            parts.append(self.shipping_state)
        if self.shipping_pincode:
            parts.append(self.shipping_pincode)

        return ", ".join(parts)

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"
    

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, 
        related_name="items", 
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.title} X {self.quantity}"


class OrderTracking(models.Model):
    order = models.ForeignKey(Order, related_name="tracking_updates", on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-time'] # Fetching order.tracking_updates.all() will show freshest status first
        constraints = [
            # Prevents duplicate tracking entries for the same state transition
            models.UniqueConstraint(
                fields=["order", "status"],
                name="unique_order_status"
            )
        ]

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
    