from django.db import models
from django.db.models import Avg
import logging

logger = logging.getLogger('store')

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ['name']

    def __str__(self):
        return self.name
    

class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.URLField()
    stock = models.PositiveIntegerField(default=0)
    reserved_stock = models.PositiveIntegerField(default=0) # locked by pending orders
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['stock']),
            models.Index(fields=['-created_at']),    # you order by this
            models.Index(fields=['price']),           # filtering/sorting
            models.Index(fields=['category']),
        ]

    @property
    def available_stock(self):
        """
        Stock available for new orders.
        = total stock minus what's already reserved
          by pending orders.
        """
        return self.stock - self.reserved_stock

    @property
    def stock_status(self):
        """
        Human-readable stock status.
        Used by frontend to show correct badge.
        """
        available = self.available_stock
        if available <= 0:
            return "out_of_stock"
        elif available <= 5:
            return "low_stock" # shows "Only X left"
        return "in_stock"

    def reserve_stock(self, quantity):
        """
        Atomically reserve stock when order is created.

        The SQL condition:
          stock >= reserved_stock + quantity
        is equivalent to:
          available_stock >= quantity

        Using F() ensures this happens in one SQL UPDATE.
        No race condition possible.

        Returns True if reservation succeeded.
        Returns False if not enough stock.
        """
        # F() expression — updates happen in SQL, not Python
        # This prevents the race condition where two reads see the same value
        from django.db.models import F

        updated = Product.objects.filter(
            id=self.id,
            # available_stock >= quantity
            # stock - reserved_stock >= quantity
            # stock >= reserved_stock + quantity
            stock__gte=F('reserved_stock') + quantity   # only update if enough stock
        ).update(
            reserved_stock=F('reserved_stock') + quantity
        )

        if updated:
            logger.debug("Stock reserved", extra={
                "product_id": self.id,
                "quantity": quantity,
            })
        else:
            logger.warning("Stock reservation failed", extra={
                "product_id": self.id,
                "quantity": quantity,
                "current_stock": self.stock,
                "current_reserved": self.reserved_stock,
            })

        return updated > 0
    
    def release_stock(self, quantity):
        """
        Release reserved stock when order is cancelled.
        Called when: order expires, user cancels, payment fails.
        """
        from django.db.models import F

        Product.objects.filter(id=self.id).update(
            reserved_stock=F('reserved_stock') - quantity
        )

        logger.debug("Stock released", extra={
            "product_id": self.id,
            "quantity": quantity,
        })

    def confirm_stock(self, quantity):
        """
        Permanently deduct stock when payment is confirmed.
        Removes both actual stock AND reservation.
        Called after successful Razorpay payment."""
        from django.db.models import F

        Product.objects.filter(id=self.id).update(
            stock=F('stock') - quantity,
            reserved_stock=F('reserved_stock') - quantity
        )

        logger.info("Stock confirmed (deducted)", extra={
            "product_id": self.id,
            "quantity": quantity,
        })
    
    @property
    def average_rating(self):
        """
        Average of all review ratings.
        Uses database AVG() — efficient for any number of reviews.
        Returns 0 if no reviews exist.

        Works because Review.product has related_name='reviews'
        which creates self.reviews reverse relation automatically.
        """
        result = self.reviews.aggregate(Avg('rating'))
        avg = result['rating__avg']
        return round(avg, 1) if avg else 0
    
    @property
    def review_count(self):
        """
        Total number of reviews.
        Uses SQL COUNT(*) — does not load review objects into memory.
        Works because Review.product has related_name='reviews'.
        """
        return self.reviews.count()

    def __str__(self):
        return self.title


class Review(models.Model):
    """
    This model creates the reverse relation on Product.

    product = ForeignKey(Product, related_name='reviews')
                                            ↑
                        This line tells Django:
                        "Add a 'reviews' attribute to Product
                        that returns all Review objects
                        for that product."

    So product.reviews.all() works WITHOUT
    any field on the Product model.
    """
    from django.core.validators import MinValueValidator, MaxValueValidator
    from django.conf import settings

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',  # ← creates Product.reviews accessor
    )
    user = models.ForeignKey(
        'accounts.User', # string reference avoids circular import
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ]
    )
    comment = models.TextField(max_length=1000)
    verified_purchase = models.BooleanField(default=True) # Set to True automatically if user has ordered this product
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'user']  # one review per user per product
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['product', '-verified_purchase']),
        ]
    
    def __str__(self):
        verified = " ✓" if self.verified_purchase else ""
        return f"{self.user.email}{verified} -> {self.product.title} ({self.rating}★)"
