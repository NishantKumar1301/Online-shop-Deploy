import uuid  # Import the uuid module
from django.urls import reverse
import stripe
import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render

from carts.models import CartItem
from orders.forms import OrderForm
from orders.models import Order, OrderProduct, Payment
from store.models import Product

from django.template.loader import render_to_string
from django.core.mail import EmailMessage

# Create your views here.

def place_order(request,  total=0, quantity=0):
    current_user=request.user

    cart_items=CartItem.objects.filter(user=current_user)
    cart_count=cart_items.count()
    if cart_count <=0:
        return redirect('store')
    
    grand_total=0
    tax=0
    
    for cart_item in cart_items:
        total += (cart_item.product.price*cart_item.quantity)
        quantity += cart_item.quantity
    tax = (3*total)/100  # 3 percent tax
    
    grand_total = total+tax
    

    if request.method=="POST":
        form =OrderForm(request.POST)
        if form.is_valid():
            data=Order()
            data.user=current_user
            data.first_name=form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total=grand_total
            data.tax=tax
            data.ip=request.META.get('REMOTE_ADDR')
            data.save()
            
            yr=int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))

            d=datetime.date(yr,mt,dt)
            current_date=d.strftime("%Y%m%d")
            order_number=current_date+str(data.id)
            data.order_number=order_number
            data.save()
            order = Order.objects.get(user=current_user,is_ordered=False,order_number=order_number)
            context={
                'order':order,
                'cart_items':cart_items,
                'total':total,
                'tax':tax,
                'grand_total':grand_total,
            }
            return render(request, 'orders/payments.html',context)

        else:
            return redirect('checkout')

def payments(request):
    return render(request,'orders/payments.html')


def calculate_grand_total(cart_items):
    total = 0
    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
    tax = (3 * total) / 100  # 3 percent tax
    grand_total = total + tax
    return grand_total

# For stripe payment
# This is your test secret API key.
from django.conf import settings
from django.views import generic
stripe.api_key = settings.STRIPE_SECRET_KEY

def generate_payment_id():
    return str(uuid.uuid4().hex)[:12]

class CreatecheckoutSessionView(generic.View):
    def post(self, request, *args, **kwargs):
        current_user = request.user
        cart_items = CartItem.objects.filter(user=request.user)
        grand_total = calculate_grand_total(cart_items)
        host = request.get_host()

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'inr',
                        'unit_amount': int(100 * grand_total),
                        'product_data': {
                            'name': f'Name: {current_user.first_name} {current_user.last_name}',
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url="http://{}{}".format(host, reverse('payment-success')),
            cancel_url="http://{}{}".format(host, reverse('payment-failure')),
        )

        return redirect(checkout_session.url, code=303)


def paymentSuccess(request):
    payment_status = 'COMPLETED'
    payment_method = 'Card'
    
    cart_items = CartItem.objects.filter(user=request.user)
    grand_total = calculate_grand_total(cart_items)
    
    payment_id = generate_payment_id()

    order = Order.objects.filter(user=request.user, is_ordered=False).first()

    if order:
        order.payment_method = payment_method
        order.status = 'Accepted'
        order.user=request.user
        order.is_ordered=True
        payment=Payment(
            user=request.user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=grand_total,
            status=payment_status
        )
        payment.save()
        order.payment=payment
        order.save() 
        
        cart_item = CartItem.objects.filter(user=request.user)
        for item in cart_item:
            orderproduct=OrderProduct()
            orderproduct.order_id=order.id
            orderproduct.payment = payment
            orderproduct.user_id = request.user.id
            orderproduct.product_id=item.product_id
            orderproduct.quantity=item.quantity
            orderproduct.product_price=item.product.price
            orderproduct.ordered=True
            orderproduct.save()
            
            cart_product=CartItem.objects.get(id=item.id)
            product_variation=cart_product.variations.all()
            orderproduct=OrderProduct.objects.get(id=orderproduct.id)
            orderproduct.variations.set(product_variation)
            orderproduct.save()
            
            product=Product.objects.get(id=item.product_id)
            product.stock-=item.quantity
            product.save()
            
        CartItem.objects.filter(user=request.user).delete()

        mail_subject = 'Thank You For Your Purchase From Our Site'
        message = render_to_string('orders/order_recieve_email.html', {
            'user': request.user,
            'order':order,
        })

        to_email = request.user.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.send()
        
        order_number=order.order_number
        transId=payment_id

        try:
            order=Order.objects.get(order_number=order_number,is_ordered=True)
            ordered_products=OrderProduct.objects.filter(order_id=order.id)
            payment=Payment.objects.get(payment_id=transId)
            
            subtotal=0
            for i in ordered_products:
                subtotal+=i.product_price*i.quantity
            context={
                'order':order,
                'order_products':ordered_products,
                'order_number': order_number,
                'transId': transId,
                'payment':payment,
                'subtotal': subtotal,
            }
            return render(request, 'orders/confirmation.html',context)

        except (Payment.DoesNotExist,Order.DoesNotExist):
            return redirect('home')
        
    return redirect('dashboard')
    



def paymentCancel(request):
    payment_status = 'Cancelled'
    payment_method = 'Card'

    cart_items = CartItem.objects.filter(user=request.user)
    grand_total = calculate_grand_total(cart_items)

    payment_id = generate_payment_id()

    order = Order.objects.filter(user=request.user, is_ordered=False).first()

    if order:
        order.payment_method = payment_method
        order.status = 'Canceled'
        order.user = request.user
        order.is_ordered = False
        payment = Payment(
            user=request.user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=grand_total,
            status=payment_status
        )
        payment.save()
        order.payment = payment
        order.save()
    
    return render(request, 'orders/cancel.html')
    
