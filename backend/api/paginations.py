from rest_framework.pagination import PageNumberPagination

from foodgram_backend.constants import PAGE_SIZE, MAX_PAGE_SIZE


class NumberPagination(PageNumberPagination):
    page_size = PAGE_SIZE
    page_query_param = 'page'
    page_size_query_param = 'limit'
    max_page_size = MAX_PAGE_SIZE
