import queue
import threading

import ply.lex as lex

from luqum.parser import parser
from luqum.thread import parse
from tests import alternative_lexer


def test_thread_parse():

    result_queue = queue.Queue()
    qs1 = """
        (title:"foo bar" AND body:"quick fox") OR title:fox AND
        (title:"foo bar" AND body:"quick fox") OR
        title:fox AND (title:"foo bar" AND body:"quick fox") OR
        title:fox AND (title:"foo bar" AND body:"quick fox") OR
        title:fox AND (title:"foo bar" AND body:"quick fox") OR title:fox
    """
    expected_tree = parser.parse(qs1)

    def run(q):
        parse(qs1)
        tree = parse(qs1)
        q.put(tree)

    # make concurrents calls
    threads = [threading.Thread(target=run, args=(result_queue,)) for i in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert result_queue.qsize() == 100
    for i in range(100):
        assert result_queue.get() == expected_tree


def test_thread_lex_global_state():
    """
    Last Lexer is used globally by default by the parser. If another library
    creates another lexer, it should not impact luqum.

    More info: [Multiple Parsers and
    Lexers](http://www.dabeaz.com/ply/ply.html#ply_nn37)
    """
    qs = '(title:"foo bar" AND body:"quick fox")'

    lex.lex(module=alternative_lexer)
    # if there is a "luqum.exceptions.ParseSyntaxError", the wrong lexer was
    # used.
    parse(qs)
