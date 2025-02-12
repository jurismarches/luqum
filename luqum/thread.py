import threading

from . import parser

thread_local = threading.local()


def parse(input=None, lexer=None, debug=False, tracking=False):
    """A (hopefully) thread safe version of :py:meth:`luqum.parser.parse`

    PLY is not thread safe because of its lexer state, but cloning it we can be
    thread safe. see: https://github.com/jurismarches/luqum/issues/72

    Warning: The parameter ``lexer``, ``debug`` and ``tracking`` are not used.
    They are still present for signature compatibility.
    """
    if not hasattr(thread_local, "lexer"):
        thread_local.lexer = parser.lexer.clone()
    return parser.parser.parse(input, lexer=thread_local.lexer)
