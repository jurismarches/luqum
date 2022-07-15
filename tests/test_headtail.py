# -*- coding: utf-8 -*-
import collections
from unittest import TestCase

from luqum.head_tail import HeadTailLexer, HeadTailManager, TokenValue
from luqum.parser import parser
from luqum.tree import (
    AndOperation, Boost, FieldGroup, Fuzzy, Group, Item, Not,
    OrOperation, Phrase, Plus, Prohibit, Proximity,
    Range, Regex, SearchField, UnknownOperation, Word,
)


class Dummy:
    def __str__(self):
        return "silly me"


class TokenValueTestCase(TestCase):

    def test_tokenvalue_str(self):
        self.assertEqual(repr(TokenValue("")), "TokenValue()")
        self.assertEqual(str(TokenValue("")), "")
        self.assertEqual(repr(TokenValue("foo")), "TokenValue(foo)")
        self.assertEqual(str(TokenValue("foo")), "foo")
        self.assertEqual(str(TokenValue(None)), "")
        self.assertEqual(str(TokenValue(Dummy())), "silly me")

    def test_tokenvalue_head_tail_pos(self):
        t = TokenValue("foo")
        self.assertEqual(t.pos, None)
        self.assertEqual(t.head, "")
        self.assertEqual(t.tail, "")


TokenMock = collections.namedtuple("TokenMock", "type value lexpos lexer")


class LexerMock:
    pass


def token_factory():
    lexer = LexerMock()

    def create_token(type_, value, lexpos):
        return TokenMock(type_, value, lexpos, lexer)

    return create_token


class HeadTailLexerTestCase(TestCase):

    handle = HeadTailLexer.handle

    def test_separator_first_in_head(self):
        for value in (TokenValue("test"), Item()):
            create_token = token_factory()
            self.handle(create_token("SEPARATOR", "\t", 0), "\t")
            token = create_token("OTHER", value, 1)
            self.handle(token, "test")
            self.assertEqual(token.value.head, "\t")
            self.assertEqual(token.value.tail, "")
            self.assertEqual(token.value.pos, 1)
            self.assertEqual(token.value.size, 4)

    def test_token_first_pos(self):
        for value in (TokenValue("test"), Item()):
            create_token = token_factory()
            token = create_token("OTHER", value, 0)
            self.handle(token, "test")
            self.assertEqual(token.value.head, "")
            self.assertEqual(token.value.tail, "")
            self.assertEqual(token.value.pos, 0)
            self.assertEqual(token.value.size, 4)

    def test_simple_token_tail(self):
        create_token = token_factory()
        a = create_token("OTHER", TokenValue("a"), 0)
        b = create_token("OTHER", Item(), 3)
        c = create_token("OTHER", TokenValue("c"), 5)
        self.handle(a, "a")
        self.handle(create_token("SEPARATOR", " \t", 1), "\t")
        self.handle(b, "")
        self.handle(create_token("SEPARATOR", "\r", 4), "\r")
        self.handle(c, "c")
        self.assertEqual(a.value.head, "")
        self.assertEqual(a.value.tail, " \t")
        self.assertEqual(a.value.pos, 0)
        self.assertEqual(a.value.size, 1)
        self.assertEqual(b.value.head, "")
        self.assertEqual(b.value.tail, "\r")
        self.assertEqual(b.value.pos, 3)
        self.assertEqual(b.value.size, 0)
        self.assertEqual(c.value.head, "")
        self.assertEqual(c.value.tail, "")
        self.assertEqual(c.value.pos, 5)
        self.assertEqual(c.value.size, 1)

    def test_separator_last_elt_none(self):
        # this is a robustness test
        for value in (TokenValue("test"), Item()):
            create_token = token_factory()
            self.handle(create_token("SEPARATOR", "\t", 0), "\t")
            self.handle(create_token("SEPARATOR", "\n", 1), "\n")
            token = create_token("OTHER", value, 2)
            self.handle(token, "test")
            self.assertEqual(token.value.head, "\t")
            self.assertEqual(token.value.tail, "")
            self.assertEqual(token.value.pos, 2)
            self.assertEqual(token.value.size, 4)

    def test_tail_at_end(self):
        create_token = token_factory()
        a = create_token("OTHER", TokenValue("a"), 0)
        b = create_token("OTHER", Item(), 3)
        self.handle(a, "a")
        self.handle(create_token("SEPARATOR", " \t", 1), "\t")
        self.handle(b, "")
        # finish with a separator
        self.handle(create_token("SEPARATOR", "\r", 4), "\r")

        self.assertEqual(a.value.head, "")
        self.assertEqual(a.value.tail, " \t")
        self.assertEqual(a.value.pos, 0)
        self.assertEqual(a.value.size, 1)
        self.assertEqual(b.value.head, "")
        self.assertEqual(b.value.tail, "\r")
        self.assertEqual(b.value.pos, 3)
        self.assertEqual(b.value.size, 0)


class HeadTailManagerTestCase(TestCase):

    headtail = HeadTailManager()

    def test_pos(self):
        p = [Item(), Item(pos=4, size=3)]
        self.headtail.pos(p)
        self.assertEqual(p[0].pos, 4)
        self.assertEqual(p[0].size, 3)

    def test_pos_without_head_transfer(self):
        p = [Item(), Item(pos=4, size=3, head="\r\n")]
        self.headtail.pos(p, head_transfer=False)
        self.assertEqual(p[0].pos, 2)
        self.assertEqual(p[0].size, 5)

    def test_pos_with_head_transfer(self):
        p = [Item(), Item(pos=4, size=3, head="\r\n")]
        self.headtail.pos(p, head_transfer=True)
        self.assertEqual(p[0].pos, 4)
        self.assertEqual(p[0].size, 3)

    def test_pos_none(self):
        p = [Item(), Item(pos=None, size=None)]
        self.headtail.pos(p)
        self.assertEqual(p[0].pos, None)
        self.assertEqual(p[0].size, 0)

    def test_binary_operation(self):
        p = [
            Item(),
            Item(pos=1, size=3, head="\t", tail="\n"),
            Item(pos=4, size=4, head="\r", tail="  "),
        ]
        self.headtail.binary_operation(p, op_tail="")
        self.assertEqual(p[0].pos, 0)
        self.assertEqual(p[0].size, 12)
        self.headtail.binary_operation(p, op_tail="  ")
        self.assertEqual(p[0].pos, 0)
        self.assertEqual(p[0].size, 10)

    def test_simple_term(self):
        p = [Item(), Item(pos=4, size=3, head="\t", tail="\r")]
        self.headtail.simple_term(p)
        self.assertEqual(p[0].head, "\t")
        self.assertEqual(p[0].tail, "\r")
        self.assertEqual(p[0].pos, 4)
        self.assertEqual(p[0].size, 3)

    def test_unary(self):
        p = [
            Item(),
            Item(head="\t", tail="\r", pos=3, size=3),
            Item(head="\n", tail="  ", pos=5, size=5),
        ]
        self.headtail.unary(p)
        self.assertEqual(p[0].head, "\t")
        self.assertEqual(p[0].tail, "")
        self.assertEqual(p[0].pos, 3)
        self.assertEqual(p[0].size, 12)
        self.assertEqual(p[2].head, "\r\n")
        self.assertEqual(p[2].tail, "  ")
        self.assertEqual(p[2].pos, 5)
        self.assertEqual(p[2].size, 5)

    def test_post_unary(self):
        p = [
            Item(),
            Item(head="\t", tail="\r", pos=3, size=3),
            Item(head="\n", tail="  ", pos=5, size=5),
        ]
        self.headtail.post_unary(p)
        self.assertEqual(p[0].head, "")
        self.assertEqual(p[0].tail, "  ")
        self.assertEqual(p[0].pos, 2)
        self.assertEqual(p[0].size, 11)
        self.assertEqual(p[1].head, "\t")
        self.assertEqual(p[1].tail, "\r\n")
        self.assertEqual(p[1].pos, 3)
        self.assertEqual(p[1].pos, 3)

    def test_paren(self):
        p = [
            Item(),  # result
            Item(head="\t", tail="\r", pos=3, size=1),  # (
            Item(head="\n", tail="  ", pos=5, size=3),  # expr
            Item(head="\n\n", tail="\t\t", pos=7, size=1),  # )
        ]
        self.headtail.paren(p)
        # result
        self.assertEqual(p[0].head, "\t")
        self.assertEqual(p[0].tail, "\t\t")
        self.assertEqual(p[0].pos, 3)
        self.assertEqual(p[0].size, 11)
        # expr
        self.assertEqual(p[2].head, "\r\n")
        self.assertEqual(p[2].tail, "  \n\n")
        self.assertEqual(p[2].pos, 5)
        self.assertEqual(p[2].size, 3)

    def test_range(self):
        p = [
            Item(),  # result
            Item(head="\t", tail="\r", pos=3, size=1),  # [
            Item(head="\n", tail="  ", pos=5, size=3),  # expr1
            Item(head="\n\n", tail="\t\t", pos=7, size=2),  # TO
            Item(head="\r\r", tail=" \t ", pos=9, size=5),  # expr2
            Item(head=" \r ", tail=" \n ", pos=12, size=1),  # ]
        ]
        self.headtail.range(p)
        # result
        self.assertEqual(p[0].head, "\t")
        self.assertEqual(p[0].tail, " \n ")
        self.assertEqual(p[0].pos, 3)
        self.assertEqual(p[0].size, 28)
        # expr1
        self.assertEqual(p[2].head, "\r\n")
        self.assertEqual(p[2].tail, "  \n\n")
        self.assertEqual(p[2].pos, 5)
        self.assertEqual(p[2].size, 3)
        # expr2
        self.assertEqual(p[4].head, "\t\t\r\r")
        self.assertEqual(p[4].tail, " \t  \r ")
        self.assertEqual(p[4].pos, 9)
        self.assertEqual(p[4].size, 5)

    def test_search_field(self):
        p = [
            Item(),  # result
            Item(head="\t", tail="\r", pos=3, size=3),  # name
            Item(head="\n", tail="  ", pos=5, size=1),  # :
            Item(head="\n\n", tail="\t\t", pos=7, size=5),  # expr
        ]
        self.headtail.search_field(p)
        # result
        self.assertEqual(p[0].head, "\t")
        self.assertEqual(p[0].tail, "")
        self.assertEqual(p[0].pos, 3)
        self.assertEqual(p[0].size, 17)
        # expr
        self.assertEqual(p[3].head, "  \n\n")
        self.assertEqual(p[3].tail, "\t\t")
        self.assertEqual(p[3].pos, 7)


class IntegrationTestCase(TestCase):

    def test_word(self):
        tree = parser.parse("\tfoo\r")
        self.assertEqual(tree, Word("foo"))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "\r")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 3)
        self.assertEqual(str(tree), "foo")
        self.assertEqual(tree.__str__(head_tail=True), "\tfoo\r")

    def test_phrase(self):
        tree = parser.parse('\t"foo  bar"\r')
        self.assertEqual(tree, Phrase('"foo  bar"'))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "\r")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 10)
        self.assertEqual(str(tree), '"foo  bar"')
        self.assertEqual(tree.__str__(head_tail=True), '\t"foo  bar"\r')

    def test_regex(self):
        tree = parser.parse('\t/foo/\r')
        self.assertEqual(tree, Regex('/foo/'))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "\r")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 5)
        self.assertEqual(str(tree), '/foo/')
        self.assertEqual(tree.__str__(head_tail=True), '\t/foo/\r')

    def test_term_to(self):
        tree = parser.parse("\tTO\r")
        self.assertEqual(tree, Word("TO"))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "\r")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 2)
        self.assertEqual(str(tree), "TO")
        self.assertEqual(tree.__str__(head_tail=True), "\tTO\r")

    def test_unknown_operator(self):
        tree = parser.parse("\tfoo\nbar\r")
        self.assertEqual(tree, UnknownOperation(Word("foo"), Word("bar")))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 9)
        foo, bar = tree.children
        self.assertEqual(foo.head, "\t")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 3)
        self.assertEqual(bar.head, "")
        self.assertEqual(bar.tail, "\r")
        self.assertEqual(bar.pos, 5)
        self.assertEqual(bar.size, 3)
        self.assertEqual(str(tree), "\tfoo\nbar\r")
        self.assertEqual(tree.__str__(head_tail=True), "\tfoo\nbar\r")

    def test_or_operator(self):
        tree = parser.parse("\tfoo\nOR  bar\rOR\t\nbaz\r\r")
        self.assertEqual(tree, OrOperation(Word("foo"), Word("bar"), Word("baz")))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 22)
        foo, bar, baz = tree.children
        self.assertEqual(foo.head, "\t")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 3)
        self.assertEqual(bar.head, "  ")
        self.assertEqual(bar.tail, "\r")
        self.assertEqual(bar.pos, 9)
        self.assertEqual(bar.size, 3)
        self.assertEqual(baz.head, "\t\n")
        self.assertEqual(baz.tail, "\r\r")
        self.assertEqual(baz.pos, 17)
        self.assertEqual(baz.size, 3)
        self.assertEqual(str(tree), "\tfoo\nOR  bar\rOR\t\nbaz\r\r")
        self.assertEqual(tree.__str__(head_tail=True), "\tfoo\nOR  bar\rOR\t\nbaz\r\r")

    def test_and_operator(self):
        tree = parser.parse("\tfoo\nAND  bar\rAND\t\nbaz\r\r")
        self.assertEqual(tree, AndOperation(Word("foo"), Word("bar"), Word("baz")))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 24)
        foo, bar, baz = tree.children
        self.assertEqual(foo.head, "\t")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 3)
        self.assertEqual(bar.head, "  ")
        self.assertEqual(bar.tail, "\r")
        self.assertEqual(bar.pos, 10)
        self.assertEqual(bar.size, 3)
        self.assertEqual(baz.head, "\t\n")
        self.assertEqual(baz.tail, "\r\r")
        self.assertEqual(baz.pos, 19)
        self.assertEqual(baz.size, 3)
        self.assertEqual(str(tree), "\tfoo\nAND  bar\rAND\t\nbaz\r\r")
        self.assertEqual(tree.__str__(head_tail=True), "\tfoo\nAND  bar\rAND\t\nbaz\r\r")

    def test_plus(self):
        tree = parser.parse("\t+\rfoo\n")
        self.assertEqual(tree, Plus(Word("foo")))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 6)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 3)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "+\rfoo\n")
        self.assertEqual(tree.__str__(head_tail=True), "\t+\rfoo\n")

    def test_minus(self):
        tree = parser.parse("\t-\rfoo\n")
        self.assertEqual(tree, Prohibit(Word("foo")))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 6)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 3)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "-\rfoo\n")
        self.assertEqual(tree.__str__(head_tail=True), "\t-\rfoo\n")

    def test_not(self):
        tree = parser.parse("\tNOT\rfoo\n")
        self.assertEqual(tree, Not(Word("foo")))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 8)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 5)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "NOT\rfoo\n")
        self.assertEqual(tree.__str__(head_tail=True), "\tNOT\rfoo\n")

    def test_group(self):
        tree = parser.parse("\t(\rfoo  )\n")
        self.assertEqual(tree, Group(Word("foo")))
        self.assertEqual(tree.head, "\t")
        self.assertEqual(tree.tail, "\n")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 8)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "  ")
        self.assertEqual(foo.pos, 3)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "(\rfoo  )")
        self.assertEqual(tree.__str__(head_tail=True), "\t(\rfoo  )\n")

    def test_search_field(self):
        # FIXME handle space between field name and ':' ?
        tree = parser.parse("\rfoo:\tbar\n")
        self.assertEqual(tree, SearchField("foo", Word("bar")))
        self.assertEqual(tree.head, "\r")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 9)
        bar, = tree.children
        self.assertEqual(bar.head, "\t")
        self.assertEqual(bar.tail, "\n")
        self.assertEqual(bar.pos, 6)
        self.assertEqual(bar.size, 3)
        self.assertEqual(str(tree), "foo:\tbar\n")
        self.assertEqual(tree.__str__(head_tail=True), "\rfoo:\tbar\n")

    def test_field_group(self):
        tree = parser.parse("\rfoo:\t(  bar\n)\t\n")
        self.assertEqual(tree, SearchField("foo", FieldGroup(Word("bar"))))
        self.assertEqual(tree.head, "\r")
        self.assertEqual(tree.tail, "")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 15)
        group, = tree.children
        self.assertEqual(group.head, "\t")
        self.assertEqual(group.tail, "\t\n")
        self.assertEqual(group.pos, 6)
        self.assertEqual(group.size, 8)
        bar, = group.children
        self.assertEqual(bar.head, "  ")
        self.assertEqual(bar.tail, "\n")
        self.assertEqual(bar.pos, 9)
        self.assertEqual(bar.size, 3)
        self.assertEqual(str(tree), "foo:\t(  bar\n)\t\n")
        self.assertEqual(tree.__str__(head_tail=True), "\rfoo:\t(  bar\n)\t\n")

    def test_range(self):
        tree = parser.parse("\r{\tfoo\nTO  bar\r\n]\t\t")
        self.assertEqual(tree, Range(Word("foo"), Word("bar"), include_low=False))
        self.assertEqual(tree.head, "\r")
        self.assertEqual(tree.tail, "\t\t")
        self.assertEqual(tree.pos, 1)
        self.assertEqual(tree.size, 16)
        foo, bar = tree.children
        self.assertEqual(foo.head, "\t")
        self.assertEqual(foo.tail, "\n")
        self.assertEqual(foo.pos, 3)
        self.assertEqual(foo.size, 3)
        self.assertEqual(bar.head, "  ")
        self.assertEqual(bar.tail, "\r\n")
        self.assertEqual(bar.pos, 11)
        self.assertEqual(bar.size, 3)
        self.assertEqual(str(tree), "{\tfoo\nTO  bar\r\n]")
        self.assertEqual(tree.__str__(head_tail=True), "\r{\tfoo\nTO  bar\r\n]\t\t")

    def test_boosting(self):
        tree = parser.parse("\rfoo\t^2\n")
        self.assertEqual(tree, Boost(Word("foo"), 2))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "\n")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 7)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\t")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "\rfoo\t^2")
        self.assertEqual(tree.__str__(head_tail=True), "\rfoo\t^2\n")

    def test_fuzzy(self):
        tree = parser.parse("\rfoo\t~2\n")
        self.assertEqual(tree, Fuzzy(Word("foo"), 2))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "\n")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 7)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\t")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 3)
        self.assertEqual(str(tree), "\rfoo\t~2")
        self.assertEqual(tree.__str__(head_tail=True), "\rfoo\t~2\n")

    def test_proximity(self):
        tree = parser.parse('\r"foo"\t~2\n')
        self.assertEqual(tree, Proximity(Phrase('"foo"'), 2))
        self.assertEqual(tree.head, "")
        self.assertEqual(tree.tail, "\n")
        self.assertEqual(tree.pos, 0)
        self.assertEqual(tree.size, 9)
        foo, = tree.children
        self.assertEqual(foo.head, "\r")
        self.assertEqual(foo.tail, "\t")
        self.assertEqual(foo.pos, 1)
        self.assertEqual(foo.size, 5)
        self.assertEqual(str(tree), '\r"foo"\t~2')
        self.assertEqual(tree.__str__(head_tail=True), '\r"foo"\t~2\n')

    def test_complex(self):
        # the scope of head / tail management is to be able to keep original structure
        # event after tree transformation or so
        query = "\rfoo AND bar  \nAND \t(\rbaz OR    spam\rOR ham\t\t)\r"
        tree = parser.parse(query)
        self.assertEqual(str(tree), query)
        self.assertEqual(tree.__str__(head_tail=True), query)

    def test_head_on_topmost(self):
        # if the head and tail is on topmost element, the str alone will strip
        query = "\r(foo AND bar  \nAND \t(\rbaz OR    spam\rOR ham\t\t))\r"
        tree = parser.parse(query)
        self.assertEqual(str(tree), query.strip())
        self.assertEqual(tree.__str__(head_tail=True), query)
