from django.urls import path
from . import api_views, views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('health/', views.health_check, name='health_check'),
    path('home/', views.home, name='home'),
    path('map/', views.map_view, name='map'),
    path('api/restaurants/map-data/', api_views.map_restaurant_data, name='api_restaurants_map'),
    path('register/', views.register, name='register'), # Removed <str:role>
    path('login/', views.user_login, name='login'),     # Removed <str:role>
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Restaurant Profile Management
    path('restaurant/profile/', views.restaurant_profile, name='restaurant_profile'),
    path('restaurant/create/', views.create_restaurant_profile, name='create_restaurant'),
    path('restaurant/edit/', views.edit_restaurant_profile, name='edit_restaurant'),
    path('restaurant/availability/', views.manage_availability, name='manage_availability'),
    path('restaurant/activate/', views.manage_activation, name='manage_activation'),
    
    # Restaurant Photo Management
    path('restaurant/photos/', views.restaurant_photos, name='restaurant_photos'),
    path('restaurant/photos/upload/', views.upload_photo, name='upload_photo'),
    path('restaurant/photos/<int:photo_id>/delete/', views.delete_photo, name='delete_photo'),
    path('restaurant/photos/<int:photo_id>/set-primary/', views.set_primary_photo, name='set_primary_photo'),
    path('search/', views.restaurant_search, name='restaurant_search'),
    # Password reset (Django built-in)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
]
