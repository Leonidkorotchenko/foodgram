import django_filters
from django_filters.rest_framework import FilterSet, filters

from .models import Ingredient, Recipe


class IngredientFilter(FilterSet):
    name = django_filters.CharFilter(field_name="name",
                                     lookup_expr="istartswith")

    class Meta:
        model = Ingredient
        fields = ("name",)


class RecipeFilter(FilterSet):
    tags = django_filters.AllValuesMultipleFilter(
        field_name='tags__slug', lookup_expr='contains'
    )
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited',
                  'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, values):
        user = self.request.user
        if values and not user.is_anonymous:
            return queryset.filter(in_favourites__user_id=user.id)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, values):
        user = self.request.user
        if values and not user.is_anonymous:
            return queryset.filter(in_shopping_list__user_id=user.id)
        return queryset
