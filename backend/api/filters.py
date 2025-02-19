from django_filters.rest_framework import FilterSet, filters

from .models import Recipe, Tag, User, Ingredient


class IngredientFilter(FilterSet):
    name = filters.CharFilter(field_name="name",
                              lookup_expr="istartswith")
    class Meta:
        model = Ingredient
        fields = ("name",)


class RecipeFilter(FilterSet):
    author = filters.ModelChoiceFilter(queryset=User.objects.all())
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
        method='filter_tags'
    )
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')
