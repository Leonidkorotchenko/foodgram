from rest_framework.pagination import PageNumberPagination


class NumberPagination(PageNumberPagination):
    page_size = 6
    page_query_param = 'page'
    page_size_query_param = 'limit'
    max_page_size = 100
