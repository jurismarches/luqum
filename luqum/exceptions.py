class InconsistentQueryException(Exception):
    """Raised when a query have a problem in its structure
    """


class OrAndAndOnSameLevel(InconsistentQueryException):
    """
    Raised when a OR and a AND are on the same level as we don't know how to
    handle this case
    """


class NestedSearchFieldException(InconsistentQueryException):
    """
    Raised when a SearchField is nested in an other SearchField as it doesn't
    make sense. For Instance field1:(spam AND field2:eggs)
    """


class ObjectSearchFieldException(InconsistentQueryException):
    """
    Raised when a doted field name is queried which is not an object field
    """
