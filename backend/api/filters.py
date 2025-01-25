from django_filters import rest_framework as filters
from .models import Tag


class TagFilter(filters.FilterSet):
    genre = filters.CharFilter(field_name='genre__slug')
    category = filters.CharFilter(field_name='category__slug')
    name = filters.CharFilter(field_name='name')
    year = filters.NumberFilter(field_name='year')

    class Meta:
        model = Tag
        fields = ['genre', 'category', 'year', 'name']