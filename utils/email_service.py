from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def send_order_confirmation_email(order, pdf_bytes=None):
    """Send order confirmation email with HTML template"""

    subject = f'Order #{order.id} Confirmed - E-Bazaar'

     # Render HTML content
    html_content = render_to_string('emails/order_confirmation.html', {
        'order': order,
        'frontend_url': settings.FRONTEND_URL,
        'user': order.user,
    })

    # Plain text fallback
    invoice_text = "Your invoice is attached to this email." if pdf_bytes else "We'll notify you when your order ships."
    text_content = f"""
    Hello {order.user.name},
    
    Your order #{order.id} has been confirmed!
    
    Order Summary:
    Total: ₹{order.grand_total}
    Status: {order.get_status_display()}
    
    We'll notify you when your order ships.
    
    Thank you for shopping with E-Bazaar!
    """

    # Create email
    email = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email]
    )
    email.attach_alternative(html_content, "text/html")

    # Dynamically attach PDF if it was generated and passed down
    if pdf_bytes:
        email.attach(
            filename=f"invoice_{order.id}.pdf",
            content=pdf_bytes,
            mimetype='application/pdf',
        )
    
    # Send email
    email.send(fail_silently=False)

    return True

def send_shipping_notification(order):
    """Send email when order ships"""

    subject = f'Your Order #{order.id} Has Shipped! 📦'

    text_content = f"""
    Hello {order.user.name}

    Great news! Your order #{order.id} has been shipped.

    Track your order at: http://localhost:5173/tracking/{order.id}

    Expected delivery: 3-5 business days
    
    Thank you for shopping with E-Bazaar!
    """

    
    email = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email]
    )
    email.send(fail_silently=False)
    
    return True
