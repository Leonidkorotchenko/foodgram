from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

from .models import User, Follow


@admin.register(User)
class AdminUser(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name",
                    "subscribers_count", "recipes_count")
    list_filter = ("username", "email", "first_name", "last_name")
    search_fields = ("username", "email", "first_name", "last_name")

    def get_queryset(self, request):
        # Аннотируем queryset дополнительными полями
        return super().get_queryset(request).annotate(
            _subscribers_count=Count('following', distinct=True),
            _recipes_count=Count('recipes', distinct=True)
        )

    # Метод для отображения подписчиков
    @admin.display(description="subscribers_count")
    def subscribers_count(self, obj):
        return obj._subscribers_count

    # Метод для отображения рецептов
    @admin.display(description="recipes_count")
    def recipes_count(self, obj):
        return obj._recipes_count


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("user", "author")
    list_filter = ("user", "author")
    search_fields = ("user", "author")
