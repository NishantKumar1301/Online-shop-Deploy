from django.shortcuts import render
from store.models import Product, ReviewRating

def home(request):
    products = Product.objects.filter(is_available=True).order_by('created_date')
    
    # Create a dictionary to hold the reviews for each product
    reviews_dict = {}
    for product in products:
        reviews_dict[product.id] = ReviewRating.objects.filter(
            product_id=product.id, status=True)
    
    context = {
        'products': products,
        'reviews_dict': reviews_dict,
    }
    
    return render(request, 'home.html', context)
