from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
	path('login/', views.login_view, name='login'),
	path('logout/', views.logout_view, name='logout'),
	path('register/', views.register_view, name='register'),
	path('username-check/', views.username_check, name='username_check'),
	path('profile/', views.profile_view, name='profile'),
	path('profile/edit/', views.profile_edit_view, name='profile_edit'),
	path('u/<str:username>/', views.profile_detail_view, name='profile_detail'),
]