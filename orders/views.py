from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
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

    def post(self, request):
        data = request.data
        items = data["items"]

        #1. Create Order
        order = Order.objects.create(
            user=request.user,
            total=data["total"],
            delivery_charges=data["delivery_charges"],
            tax=data["tax"],
            grand_total=data["grand_total"],
        )

        #2. Create Order Items
        for item in items:
            product = Product.objects.get(id=item["product"])
            OrderItem.objects.create(
                order=order, 
                product=product,
                quantity=item["quantity"],
                price=item["price"],
            )

        # Add initial tracking update
        OrderTracking.objects.create(order=order, status="Pending")

        #3. Create Razorpay order
        amount = int(order.grand_total * 100) #Razorpay works in paise
        razorpay_order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1
        })

        #4. Create Payment entry
        Payment.objects.create(
            order=order,
            razorpay_order_id=razorpay_order["id"],
            amount=order.grand_total
        )

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
            return Response({"message": "Payment verified successfully"})
        
        except:
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
    if data["event"] == "payment.captured":
        razorpay_order_id = data["payload"]["payment"]["entity"]["order_id"]

        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
        # Prevent double update
        if payment.status != "SUCCESS":
            payment.status = "SUCCESS"
            payment.save()

            payment.order.status = "CONFIRMED"
            payment.order.save()

    return JsonResponse({"status": "ok"})