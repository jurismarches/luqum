import queue
import threading

from luqum.parser import parser
from luqum.thread import parse


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
    assert result_queue.qsize() == 100
    for i in range(100):
        assert result_queue.get() == expected_tree
