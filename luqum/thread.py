import threading

from ply import lex

from . import parser


thread_local = threading.local()


def parse(input=None, lexer=None, debug=False, tracking=False):
    """A (hopefully) thread safe version of :py:meth:`luqum.parser.parse`

    PLY is not thread safe because of its lexer state, but cloning it we can be thread safe.
    see: https://github.com/jurismarches/luqum/issues/72
    """
    if not hasattr(thread_local, "lexer"):
        thread_local.lexer = lex.lexer.clone()
    return parser.parser.parse(input, lexer=thread_local.lexer)
