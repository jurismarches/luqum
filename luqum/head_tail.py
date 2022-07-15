"""Utilities to manage head and tail of elements

The scope is to avoid loosing part of the original text in the final tree.
"""
from .tree import Item


class TokenValue:

    def __init__(self, value):
        self.value = value
        self.pos = None
        self.size = None
        self.head = ""
        self.tail = ""

    def __repr__(self):
        return "TokenValue(%s)" % self.value

    def __str__(self):
        return str(self.value) if self.value else ""


class HeadTailLexer:
    """Utility to handle head and tail at lexer time.
    """

    LEXER_ATTR = "_luqum_headtail"

    @classmethod
    def handle(cls, token, orig_value):
        """Handling a token.

        .. note::
          PLY does not gives acces to previous tokens,
          although it does not provide any infrastructure for handling specific state.

          So we use the strategy
          of puting a :py:cls:`HeadTailLexer`instance as an attribute of the lexer
          each time we start a new tokenization.
        """
        # get instance
        if token.lexpos == 0:
            # first token make instance
            instance = cls()
            setattr(token.lexer, cls.LEXER_ATTR, instance)
        else:
            instance = getattr(token.lexer, cls.LEXER_ATTR)
        # handle
        instance.handle_token(token, orig_value)

    def __init__(self):
        self.head = None
        """This will track the head of next element, useful only for first element
        """
        self.last_elt = None
        """This will track the last token, so we can use it to add the tail to it.
        """

    def handle_token(self, token, orig_value):
        """Handle head and tail for tokens

        The scope is to avoid loosing part of the original text and keep it in elements.
        """
        # handle headtail
        if token.type == "SEPARATOR":
            if token.lexpos == 0:
                # spaces at expression start, head for next token
                self.head = token.value
            else:
                # tail of last processed token
                if self.last_elt is not None:
                    self.last_elt.value.tail += token.value
        else:
            # if there is a head, apply
            head = self.head
            if head is not None:
                token.value.head = head
                self.head = None
            # keep tracks of token, to apply tail later
            self.last_elt = token
        # also set pos and size
        if isinstance(token.value, (Item, TokenValue)):
            token.value.pos = token.lexpos
            token.value.size = len(orig_value)


token_headtail = HeadTailLexer.handle


class HeadTailManager:
    """Utility to hande head and tail at expression parse time
    """

    def pos(self, p, head_transfer=False, tail_transfer=False):
        """Compute pos and size of element 0 based on it's parts (p[1:])

        :param list p: the parser expression as in PLY
        :param bool head_transfer: True if head of first child will be transfered to p[0]
        :param bool tail_transfer: True if tail of last child wiil be transfered to p[0]
        """
        # pos
        if p[1].pos is not None:
            p[0].pos = p[1].pos
            if not head_transfer:
                # head is'nt transfered, so we are before it
                p[0].pos -= len(p[1].head)
        # size
        p[0].size = sum(
            (elt.size or 0) + len(elt.head or "") + len(elt.tail or "") for elt in p[1:])
        if head_transfer and p[1].head:
            # we account head in size, remove it
            p[0].size -= len(p[1].head)
        last_p = p[len(p) - 1]  # negative indexing not supported by PLY
        if tail_transfer and last_p.tail:
            # we account head in size, remove it
            p[0].size -= len(last_p.tail)

    def binary_operation(self, p, op_tail):
        self.pos(p, head_transfer=False, tail_transfer=False)
        # correct size
        p[0].size -= len(op_tail)

    def simple_term(self, p):
        self.pos(p, head_transfer=True, tail_transfer=True)
        p[0].head = p[1].head
        p[0].tail = p[1].tail

    def unary(self, p):
        """OP expr"""
        self.pos(p, head_transfer=True, tail_transfer=False)
        p[0].head = p[1].head
        p[2].head = p[1].tail + p[2].head

    def post_unary(self, p):
        """expr OP"""
        self.pos(p, head_transfer=False, tail_transfer=True)
        p[1].tail += p[2].head
        p[0].tail = p[2].tail

    def paren(self, p):
        """( expr )"""
        self.pos(p, head_transfer=True, tail_transfer=True)
        # p[0] is global element (Group or FieldGroup)
        # p[2] is content
        # p[1] is left parenthesis
        p[0].head = p[1].head
        p[2].head = p[1].tail + p[2].head
        # p[3] is right parenthesis
        p[2].tail += p[3].head
        p[0].tail = p[3].tail

    def range(self, p):
        """[ expr TO expr ]"""
        self.pos(p, head_transfer=True, tail_transfer=True)
        # p[0] is global element (Range)
        # p[2] is lower bound
        p[0].head = p[1].head
        p[2].head = p[1].tail + p[2].head
        # p[3] is TO
        # p[4] is upper bound
        p[2].tail += p[3].head
        p[4].head = p[3].tail + p[4].head
        # p[5] is upper braket
        p[4].tail += p[5].head
        p[0].tail = p[5].tail

    def search_field(self, p):
        """name: expr"""
        self.pos(p, head_transfer=True, tail_transfer=False)
        # p[0] is global element (SearchField)
        # p[1] is search field name
        # p[2] is COLUMN
        p[0].head = p[1].head
        if p[1].tail or p[2].head:
            pass  # FIXME: add warning, or handle space between point and name in SearchField ?
        # p[3] is the expression
        p[3].head = p[2].tail + p[3].head


head_tail = HeadTailManager()
"""singleton of HeadTailManager
"""
