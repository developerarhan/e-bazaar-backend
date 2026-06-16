from django.urls import path

from .views import (
    CategoryListView,
    ProductListView, 
    ProductDetailView,
    ProductStockView,
    ReviewListCreateView,
    ReviewDetailView,
    RelatedProductsView,
)

urlpatterns = [
    # Products
    path("", ProductListView.as_view(), name="products"),
    path("<int:pk>/", ProductDetailView.as_view(), name="products-detail"),
    path("<int:pk>/related/", RelatedProductsView.as_view()), 

    # Live stock
    path("<int:pk>/stock/", ProductStockView.as_view(), name="product-stock"),

    # Reviews
    path("<int:pk>/reviews/", ReviewListCreateView.as_view(), name="product-reviews"),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),

    # Categories
    path("categories/", CategoryListView.as_view(), name="categories"),
]