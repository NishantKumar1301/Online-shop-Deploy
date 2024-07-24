from . import views
from django.urls import path

urlpatterns = [
    path('place_order/', views.place_order, name='place_order'),
    path('payments/',views.payments,name="payments"),
    path('create-checkout-session/', views.CreatecheckoutSessionView.as_view(),name="create-checkout-session"),
    path('success/', views.paymentSuccess, name="payment-success"),
    path('failure/', views.paymentCancel, name="payment-failure"),
]
