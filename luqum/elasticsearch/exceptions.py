class OrAndAndOnSameLevel(Exception):
    """
    Raised when a OR and a AND are on the same level as we don't know how to
    handle this case
    """
    pass


class NestedSearchFieldException(Exception):
    """
    Raised when a SearchField is nested in an other SearchField as it doesn't
    make sense. For Instance field1:(spam AND field2:eggs)
    """
    pass
