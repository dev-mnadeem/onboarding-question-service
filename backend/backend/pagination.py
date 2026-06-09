from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a caller-controlled, capped page size.

    Applied project-wide through ``REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]``
    so no list endpoint can return an unbounded result set.
    """

    page_size_query_param = "page_size"
    max_page_size = 100
