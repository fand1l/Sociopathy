from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
	path('login/', views.LoginView.as_view(), name='login'),
	path('logout/', views.LogoutView.as_view(), name='logout'),
	path('register/', views.RegisterView.as_view(), name='register'),
	path('username-check/', views.UsernameCheckView.as_view(), name='username_check'),
	path('preferences/', views.ThemePreferencesView.as_view(), name='theme_preferences'),
	path('profile/', views.ProfileView.as_view(), name='profile'),
	path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
	path('u/<str:username>/', views.ProfileDetailView.as_view(), name='profile_detail'),
]