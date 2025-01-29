from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import (Favourites, Ingredient, Recipe, IngredientInRecipe,
                     ShoppingCart, Tag)


class RecipeIngredientInline(admin.TabularInline):
    model = IngredientInRecipe
    extra = 1
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "author", "cooking_time",
                    "favorite_count", "tags_list",)
    list_filter = ("name", "author", "tags")
    search_fields = ("name", "author", "tags")
    inlines = (RecipeIngredientInline,)
    empty_value_display = "-пусто-"

    @admin.display(description='Количество в избранных')
    def favorite_count(self, obj):
        """Получаем количество избранных."""
        return obj.in_favourites.count()

    @admin.display(description='Теги')
    @mark_safe
    def tags_list(self, recipe):
        return '<br>'.join(tag.name for tag in recipe.tags.all())


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "measurement_unit")
    list_filter = ("name",)
    search_fields = ("name",)
    empty_value_display = "-пусто-"


@admin.register(IngredientInRecipe)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "amount")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    list_filter = ("name",)
    search_fields = ("name",)
    empty_value_display = "-пусто-"


@admin.register(Favourites)
class FavouritesAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe")


@admin.register(ShoppingCart)
class Shopping_cartAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe")
