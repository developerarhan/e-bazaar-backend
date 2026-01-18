from django.urls import path
from .views import UserOrdersView, OrderDetailView, CreateOrderPaymentView, VerifyPaymentView, razorpay_webhook_view

urlpatterns = [
    path("payment/create/", CreateOrderPaymentView.as_view()),
    path("my-orders/", UserOrdersView.as_view()),
    path("<int:pk>/", OrderDetailView.as_view()),
    path("payment/verify/", VerifyPaymentView.as_view()),
    path("payment/webhook/", razorpay_webhook_view),
]