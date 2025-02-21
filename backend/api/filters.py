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
        queryset=Tag.objects.all(),
        field_name='tags__slug',
        to_field_name='slug',
    )
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(in_favorites__user=self.request.user)
        return queryset

    def filter_shopping_cart(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(in_shopping_carts__user=self.request.user)
        return queryset
