from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import razorpay
import hmac
import hashlib
import json

from store.models import Product
from .models import Order, OrderItem, OrderTracking, Payment
from .serializers import OrderSerializer
# Create your views here.   

class UserOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by("-id")
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
    

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        order = Order.objects.get(pk=pk, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)
    

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreateOrderPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data
        items = data["items"]

        # Check for existing pending order
        order = Order.objects.filter(
            user=request.user,
            status="PENDING_PAYMENT"
        ).last()

        if not order:
            order = Order.objects.create(
                user=request.user,
                total=data["total"],
                delivery_charges=data["delivery_charges"],
                tax=data["tax"],
                grand_total=data["grand_total"],
            )
        else:
            #IMPORTANT: Update total on retry
            order.total=data["total"]
            order.delivery_charges=data["delivery_charges"]
            order.tax=data["tax"]
            order.grand_total=data["grand_total"]
            order.save()

        OrderItem.objects.filter(order=order).delete()

        for item in items:
            product = Product.objects.get(id=item["product"])
            OrderItem.objects.create(
                order=order, 
                product=product,
                quantity=item["quantity"],
                price=item["price"],
            )

        # Add initial tracking update
        if not OrderTracking.objects.filter(order=order).exists():
            OrderTracking.objects.create(order=order, status="Pending Payment")

        amount = int(order.grand_total * 100) #Razorpay works in paise

        # Check if any PENDING payment already exists
        payment = Payment.objects.filter(order=order, status="CREATED").first()

        #3. Create Razorpay order
        if not payment:
            razorpay_order = client.order.create({
                "amount": amount,
                "currency": "INR",
                "payment_capture": 1
            })

            #4. Create Payment entry
            payment = Payment.objects.create(
                order=order,
                razorpay_order_id=razorpay_order["id"],
                amount=order.grand_total,
                status="CREATED"
            )
        else:
            razorpay_order = {
                "id": payment.razorpay_order_id
            }

        #5. Send to frontend
        return Response({
            "razorpay_order_id": razorpay_order["id"],
            "amount": amount,
            "key": settings.RAZORPAY_KEY_ID,
            "order_id": order.id
        })
    

class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            })

            payment = Payment.objects.get(razorpay_order_id=data['razorpay_order_id'])
            # Already processed? Skip
            if payment.status == "SUCCESS":
                return Response({"message": "Payment already verified"})
            
            payment.razorpay_payment_id = data['razorpay_payment_id']
            payment.razorpay_signature = data['razorpay_signature']
            payment.status = "SUCCESS"
            payment.save()

            order = payment.order
            order.status = "CONFIRMED"
            order.save()

            if not OrderTracking.objects.filter(
                order=order,
                status="Confirmed"
            ).exists():
                OrderTracking.objects.create(order=order, status="Confirmed")

            return Response({"message": "Payment verified successfully"})
        
        except:
            payment = Payment.objects.filter(
                razorpay_order_id=data.get("razorpay_order_id")
            ).first()
            if payment:
                payment.status = "FAILED"
                payment.save()
            return Response({"error": "Payment verification failed"}, status=400)
        

@csrf_exempt
def razorpay_webhook_view(request):
    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    secret = settings.RAZORPAY_WEBHOOK_SECRET

    expected_signature = hmac.new(
        bytes(secret, 'utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if expected_signature != signature:
        return JsonResponse({"status": "Invalid signature"}, status=400)
    
    data = json.loads(payload)

    razorpay_order_id = (
        data.get("payload", {})
        .get("payment", {})
        .get("entity", {})
        .get("order_id")
    )

    payment = Payment.objects.filter(
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