from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Sum, Count
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import Order, OrderItem
from utils.email_service import send_order_confirmation_email, send_shipping_notification

logger = logging.getLogger('orders')

@shared_task(
    bind=True, 
    max_retries=3,
    default_retry_delay=60,     # wait 60 seconds before retry
    name='orders.send_confirmation_email'
)
def send_order_confirmation_task(self, order_id):
    """
    Send order confirmation email.
    Retries 3 times with 60 second delay if it fails. (email server down, etc.)
    """
    try:
        from orders.invoice import generate_invoice_pdf

        order = Order.objects.select_related(
            'user'
        ).prefetch_related(
            'items__product'
        ).get(id=order_id)

        # Generate PDF invoice in-memory
        pdf_bytes = generate_invoice_pdf(order)

        send_order_confirmation_email(order, pdf_bytes=pdf_bytes)

        logger.info("Order confirmation email sent", extra={
            "order_id": order_id,
            "user_id": order.user.id,
            "email": order.user.email,
        })

        return f"Confirmation + invoice sent for order {order_id}"

    
    except Order.DoesNotExist:
        # Don't retry — if order doesn't exist now it won't later
        logger.error("Order not found for confirmation email", extra={
            "order_id": order_id,
        })
        return f"Order {order_id} not found — no retry"
    
    except Exception as exc:
        logger.error("Failed to send confirmation email", extra={
            "order_id": order_id,
            "error": str(exc),
            "attempt": self.request.retries + 1,
            "max_retries": self.max_retries,
        })
        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300)
    

@shared_task(
    bind=True,  # ← add bind=True so we have access to self
    max_retries=3,  # ← add retry logic
    default_retry_delay=60,
    name='orders.send_shipping_notification'
)
def send_shipping_notification_task(self, order_id):
    """Send email when order status changes to SHIPPED"""
    try:
        order = Order.objects.select_related('user').get(id=order_id)
        send_shipping_notification(order)

        logger.info("Shipping notification sent", extra={
            "order_id": order_id,
            "user_id": order.user.id,
        })

        return f"Shipping notification sent for order {order_id}"
    
    except Exception as exc:
        logger.error("Failed to send shipping notification", extra={
            "order_id": order_id,
            "error": str(exc),
        })
        raise self.retry(exc=exc)


@shared_task(name='orders.expire_pending_orders')
def expire_pending_orders():
    """
    Runs every 15 minutes.
    Cancels orders that have been PENDING_PAYMENT for more than 30 minutes.
    This frees up inventory and keeps our database clean.
    """
    expiry_time = timezone.now() - timedelta(minutes=30)
    updated_count = 0

    # Get IDs first — snapshot of what to expire RIGHT NOW
    # This prevents the race condition where a user pays
    # between our filter and our update
    # Encapsulate the checkout checks and mutations inside an atomic sequence
    with transaction.atomic():
        expired_orders = Order.objects.select_for_update().filter(
            status="PENDING_PAYMENT",
            created_at__lt=expiry_time
        )

        if not expired_orders:
            logger.info("No pending orders to expire")
            return 0

        for order in expired_orders:
            for item in order.items.select_related('product'):
                item.product.release_stock(item.quantity)

        # Batch execute the cancellation status change cleanly
        updated_count = expired_orders.update(status='CANCELLED')

    logger.info("Expired pending orders", extra={
        "expired_count": updated_count,
    })
    
    return updated_count
