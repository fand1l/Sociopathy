from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile

# 1. Робимо профіль доступним прямо в редагуванні юзера
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профіль'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_bio')
    list_select_related = ('profile', ) # Оптимізація запитів до бази

    # Дозволяє вивести поле з профілю в список юзерів
    def get_bio(self, instance):
        return instance.profile.bio
    get_bio.short_description = 'Біографія'

    # Важливо: щоб inline працював правильно з OneToOneField
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)

# 3. Реєструємо моделі
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Profile) # Можна зареєструвати і окремо для швидкого доступу