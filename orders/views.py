from django.db import transaction
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import ValidationError
import razorpay
from razorpay.errors import SignatureVerificationError
import hmac
import hashlib
import json
import logging
import re
from decimal import Decimal

from store.models import Product
from .models import Order, OrderItem, OrderTracking, Payment
from .serializers import OrderSerializer
from .tasks import send_order_confirmation_task, send_shipping_notification_task


# This is the standard pattern — one logger per file
# The name matches what you defined in LOGGING['loggers']
logger = logging.getLogger('orders')

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

DELIVERY_CHARGE_THRESHOLD = Decimal("500.00")
DELIVERY_CHARGE = Decimal("50.00")
TAX_RATE = Decimal("0.05")  # 5 percent

PINCODE_PATTERN = re.compile(r'^\d{6}$')
PHONE_PATTERN = re.compile(r'^[6-9]\d{9}$') 



def calculate_totals(items_data):
    """
    Calculate order totals from validated items.
    All values come from the database, not the client.
    """
    subtotal = sum(
        item["price"] * item["quantity"]
        for item in items_data
    )

    delivery_charges = (
        Decimal("0.00")
        if subtotal > DELIVERY_CHARGE_THRESHOLD
        else DELIVERY_CHARGE
    )

    tax = (subtotal + delivery_charges) * TAX_RATE
    tax = tax.quantize(Decimal("0.01"))

    grand_total = subtotal + delivery_charges + tax

    return {
        "total": subtotal,
        "delivery_charges": delivery_charges,
        "tax": tax,
        "grand_total": grand_total,
    }

def validate_shipping_details(shipping):
    """
    Validates shipping dict from request data.
    Raises ValidationError with a clear message if invalid.
    Returns a cleaned dict ready to save on Order.
    """
    required_fields = ['name', 'phone', 'address', 'city', 'state', 'pincode']

    for field in required_fields:
        value = shipping.get(field, '').strip() if isinstance(shipping.get(field), str) else shipping.get(field)
        if not value:
            raise ValidationError(f"Shipping field '{field}' is required.")

    name = shipping['name'].strip()
    phone = shipping['phone'].strip()
    address = shipping['address'].strip()
    city = shipping['city'].strip()
    state = shipping['state'].strip()
    pincode = shipping['pincode'].strip()

    if len(name) < 2:
        raise ValidationError("Name must be at least 2 characters.")
    
    if not PHONE_PATTERN.match(phone):
        raise ValidationError("Enter a valid 10-digit mobile number.")
    
    if not PINCODE_PATTERN.match(pincode):
        raise ValidationError("Enter a valid 6-digit pincode.")
    
    if len(address) < 5:
        raise ValidationError("Address is too short.")
    
    return {
        'shipping_name': name,
        'shipping_phone': phone,
        'shipping_address': address,
        'shipping_city': city,
        'shipping_state': state,
        'shipping_pincode': pincode,
    }


class UserOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related(
            'items__product',
            'tracking_updates',
        ).order_by("-id")
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
    

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items__product', 'tracking_updates').get(pk=pk, user=request.user)
            serializer = OrderSerializer(order)
            return Response(serializer.data)
        except Order.DoesNotExist:
            return Response({"error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)
    

class CreateOrderPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Log the start of an important operation
        # extra={} is where structured data goes — searchable in log tools
        logger.info("Order creation initiated", extra={
            "user_id": request.user.id,
            "item_count": len(request.data.get("items", [])),
            "grand_total": request.data.get("grand_total"),
        })

        data = request.data
        items = data.get("items", [])
        shipping_data = data.get("shipping")

        if not items:
            return Response(
                {"error": "No items provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not shipping_data:
            return Response(
                {"error": "Shipping details are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            items = sorted(items, key=lambda x: int(x["product"]))
        except (ValueError, KeyError):
            return Response({"error": "Invalid product data structure"}, 
            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate incoming shipping fields before database execution
            cleaned_shipping = validate_shipping_details(shipping_data)
            
            # Prevent Deadlocks: Sort incoming items by product ID sequentially
            
            # PHASE 1: DB Operations (Atomic Block handles quick writes, no network calls)
            with transaction.atomic():
                validated_items = []

                for item in items:
                    # Validate item structure
                    if "product" not in item or "quantity" not in item:
                        raise ValidationError("Each item needs 'product' and 'quantity'")
                
                    quantity = int(item["quantity"])
                    if quantity < 1 :
                        raise ValidationError("Quantity must be at least 1")
                
                # Row-locking sequentially by product ID
                    try:
                        product = Product.objects.select_for_update().get(
                            id=item["product"]
                        )
                    except Product.DoesNotExist:
                        raise ValidationError(f"Product {item['product']} not found")
                    
                # Check available stock (not total stock)
                    if product.available_stock < quantity:
                        # DRF ValidationError accepts dictionaries for structured error messages
                        raise ValidationError({
                            "error": f"Insufficient stock for '{product.title}'",
                            "available": product.available_stock,
                            "requested": quantity,
                        })
                    
                    validated_items.append({
                        "product": product,
                        "quantity": quantity,
                        "price": product.price,  # always from database
                    })

                totals = calculate_totals(validated_items)

                order = Order.objects.select_for_update().select_related(
                    'user'
                ).filter(
                    user=request.user,
                    status="PENDING_PAYMENT"
                ).last()

                if not order:
                    order = Order.objects.create(
                        user=request.user,
                        **totals,
                        **cleaned_shipping
                    )
                    logger.info("New order created", extra={
                        "order_id": order.id,
                        "user_id": request.user.id,
                        "grand_total": str(order.grand_total),
                    })

                else:
                    # Release previously reserved stock before clearing items
                    old_items = OrderItem.objects.filter(
                        order=order
                    ).select_related('product')

                    for old_item in old_items:
                        old_item.product.release_stock(old_item.quantity)

                    # Update order totals
                    for field, value in totals.items():
                        setattr(order, field, value)

                    # Update old pending order fields with the latest shipping details
                    for field, value in cleaned_shipping.items():
                        setattr(order, field, value)
                        
                    order.status = "PENDING_PAYMENT"
                    order.save()

                    # Delete old payment and items
                    Payment.objects.filter(order=order, status="CREATED").delete()
                    OrderItem.objects.filter(order=order).delete()
                    
                    logger.info("Reusing existing pending order", extra={
                        "order_id": order.id,
                        "user_id": request.user.id,
                    })

                for item_data in validated_items:
                    # reserve_stock uses an atomic F() expression safely
                    reserved = item_data["product"].reserve_stock(
                        item_data["quantity"]
                    )

                    if not reserved:
                        # Race condition — another request grabbed stock
                        # transaction.atomic will rollback everything above
                        logger.warning("Stock reservation failed - race condition", extra={
                            "product_id": item_data["product"].id,
                            "quantity": item_data["quantity"],
                            "user_id": request.user.id,
                        })
                        raise ValidationError(
                            f"Stock just ran out for "
                            f"'{item_data['product'].title}'. "
                            f"Please try again."
                        )
                    
                    OrderItem.objects.create(
                        order=order,
                        product=item_data["product"],
                        quantity=item_data["quantity"],
                        price=item_data["price"],
                    )

                OrderTracking.objects.get_or_create(order=order, status="Pending Payment")
                amount = int(order.grand_total * Decimal("100"))
                order_id = order.id

            # PHASE 2: External Payment API Call (Safely decoupled from active DB transactions)
            payment = Payment.objects.filter(
                order=order,
                status="CREATED"
            ).first()

            if not payment:
                try:
                    razorpay_order = client.order.create({
                        "amount": amount,
                        "currency": "INR",
                        "payment_capture": 1
                    })

                    # Tiny atomic transaction block just to store the payment record
                    with transaction.atomic():
                        payment, created = Payment.objects.get_or_create(
                            order=order,
                            razorpay_order_id=razorpay_order["id"],
                            amount=order.grand_total,
                            status="CREATED"
                        )
                        if not created:
                            razorpay_order = {"id": payment.razorpay_order_id}

                    logger.info("Razorpay order created", extra={
                        "order_id": order.id,
                        "razorpay_order_id": razorpay_order["id"],
                        "amount": amount,
                    })
                except Exception as e:
                    logger.error("Razorpay order creation failed", exc_info=True)
                    return Response({"error": "Payment gateway down"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            else:
                razorpay_order = {"id": payment.razorpay_order_id}

            return Response({
                "razorpay_order_id": razorpay_order["id"],
                "amount": amount,
                "key": settings.RAZORPAY_KEY_ID,
                "order_id": order.id
            })             
        except ValidationError as e:
            logger.warning("Validation error during order creation", extra={
                "user_id": request.user.id,
                "error": str(e),
            })
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )       
        except Exception as e:
            # Unexpected errors — log as error with full traceback
            # exc_info=True tells the logger to include the full stack trace
            logger.error("Unexpected error during order creation", extra={
                "user_id": request.user.id,
                "error": str(e),
            }, exc_info=True)
            return Response(
                {"error": "Something went wrong. Please try again."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data

        logger.info("Payment verification initiated", extra={
            "user_id": request.user.id,
            "razorpay_order_id": data['razorpay_order_id'],
        })

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            })

            payment = Payment.objects.select_for_update().get(
                razorpay_order_id=data['razorpay_order_id']
            )

            if payment.status == "SUCCESS":
                logger.warning("Duplicate payment verification attempt", extra={
                    "user_id": request.user.id,
                    "razorpay_order_id": data['razorpay_order_id'],
                    "payment_id": payment.id,
                })
                return Response({"message": "Payment already verified"})

            payment.razorpay_payment_id = data['razorpay_payment_id']
            payment.razorpay_signature = data['razorpay_signature']
            payment.status = "SUCCESS"
            payment.save()

            order = payment.order

            if order.status != "CONFIRMED":
                order.status = "CONFIRMED"
                order.save()

                # This is the most important business event — log it clearly
                logger.info("Payment verified successfully", extra={
                    "user_id": request.user.id,
                    "order_id": order.id,
                    "payment_id": payment.id,
                    "razorpay_order_id": data['razorpay_order_id'],
                    "amount": str(payment.amount),
                })

                OrderTracking.objects.get_or_create(
                    order=order,
                    status="Confirmed"
                )

                # Dispatch task only AFTER the database commits the transaction safely
                transaction.on_commit(lambda: send_order_confirmation_task.delay(order.id))

            return Response({"message": "Payment verified successfully"})

        except SignatureVerificationError:
            payment = Payment.objects.filter(
                razorpay_order_id=data.get("razorpay_order_id")
            ).first()

            if payment:
                payment.status = "FAILED"
                payment.save()

            return Response({"error": "Payment verification failed"}, status=400)

        except KeyError as e:
            # logger.error(f"Missing field in payment data: {e}")
            return Response({"error": "Invalid request data"}, status=400)

        except Exception as e:
            # logger.exception(f"Unexpected error in payment verification: {e}")
            return Response({"error": "Internal server error"}, status=500)      

@csrf_exempt
@transaction.atomic
def razorpay_webhook_view(request):
    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    secret = settings.RAZORPAY_WEBHOOK_SECRET

    expected_signature = hmac.new(
        key=bytes(secret, 'utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Also use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, signature):
        return JsonResponse({"status": "Invalid signature"}, status=400)
    
    data = json.loads(payload)

    razorpay_order_id = (
        data.get("payload", {})
        .get("payment", {})
        .get("entity", {})
        .get("order_id")
    )

    payment = Payment.objects.select_for_update().select_related('order').filter(
        razorpay_order_id=razorpay_order_id
    ).first()

    if not payment:
        return JsonResponse({"status": "payment not found"}, status=404)

    if data["event"] == "payment.captured":
        # Prevent double update
        if payment.status != "SUCCESS":
            payment.status = "SUCCESS"
            payment.save()

            order = payment.order
            order.status = "CONFIRMED"
            order.save()

            if not OrderTracking.objects.filter(
                order=order,
                status="Confirmed"
            ).exists():
                OrderTracking.objects.create(order=payment.order, status="Confirmed")

    elif data["event"] == "payment.failed":
        if payment.status != "FAILED": 
            payment.status = "FAILED"
            payment.save()

            payment.order.status = "PENDING_PAYMENT"
            payment.order.save()

    return JsonResponse({"status": "ok"})


class ShipOrderView(APIView):
    """Admin endpoint to mark order as shipped"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)

            if order.status != 'CONFIRMED':
                return Response(
                    {"error": "Only confirmed orders can be shipped"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = 'SHIPPED'
            order.save()

            OrderTracking.objects.create(order=order, status="Shipped")

            send_shipping_notification_task.delay(order.id)

            return Response({
                "message": "Order marked as shipped, notification sent",
                "order_id": order.id
            })
        
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
from django.http import HttpResponse
from .invoice import generate_invoice_pdf


class OrderInvoiceView(APIView):
    """
    GET /api/orders/<id>/invoice/

    Returns the PDF invoice for download.
    Only the order's owner can access it.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = Order.objects.select_related('user').prefetch_related(
                'items__product'
            ).get(id=pk, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Don't generate invoices for unpaid orders
        if order.status == "PENDING_PAYMENT":
            return Response(
                {"error": "Invoice not available until payment is confirmed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pdf_bytes = generate_invoice_pdf(order)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="invoice_{order.id}.pdf"'
        )

        logger.info("Invoice downloaded", extra={
            'order_id': order.id,
            'user_id': request.user.id,
        })

        return response
    