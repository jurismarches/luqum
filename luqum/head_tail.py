"""Utilities to manage head and tail of elements

The scope is to avoid loosing part of the original text in the final tree.
"""
from .tree import Item


class TokenValue:

    def __init__(self, value):
        self.value = value
        self.pos = None
        self.head = ""
        self.tail = ""

    def __repr__(self):
        return "TokenValue(%s)" % self.value

    def __str__(self):
        return self.value


class HeadTailLexer:
    """Utility to handle head and tail at lexer time
    """

    LEXER_ATTR = "_luqum_headtail"

    @classmethod
    def handle(cls, token):
        # get instance
        if token.lexpos == 0:
            # first token make instance
            instance = cls()
            setattr(token.lexer, cls.LEXER_ATTR, instance)
        else:
            instance = getattr(token.lexer, cls.LEXER_ATTR)
        # handle
        instance.handle_token(token)

    def __init__(self):
        self.head = None
        self.last_elt = None

    def handle_token(self, token):
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
        # also set pos
        if isinstance(token.value, (Item, TokenValue)):
            token.value.pos = token.lexpos


token_headtail = HeadTailLexer.handle


class HeadTailManager:
    """Utility to hande head and tail at expression parse time
    """

    def pos(self, p, head_transfer=False):
        if p[1].pos is not None:
            p[0].pos = p[1].pos
            if not head_transfer:
                # head won't be transfered
                p[0].pos -= len(p[1].head)

    def simple_term(self, p):
        p[0].head = p[1].head
        p[0].tail = p[1].tail
        self.pos(p, head_transfer=True)

    def unary(self, p):
        """OP expr"""
        p[0].head = p[1].head
        p[2].head = p[1].tail + p[2].head
        self.pos(p, head_transfer=True)

    def post_unary(self, p):
        """expr OP"""
        p[1].tail += p[2].head
        p[0].tail = p[2].tail
        self.pos(p, head_transfer=False)

    def paren(self, p):
        """( expr )"""
        # p[0] is global element (Group or FieldGroup)
        # p[2] is content
        # p[1] is left parenthesis
        p[0].head = p[1].head
        p[2].head = p[1].tail + p[2].head
        # p[3] is right parenthesis
        p[2].tail += p[3].head
        p[0].tail = p[3].tail
        self.pos(p, head_transfer=True)

    def range(self, p):
        """[ expr TO expr ]"""
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
        self.pos(p, head_transfer=True)

    def search_field(self, p):
        """name: expr"""
        # p[0] is global element (SearchField)
        # p[1] is search field name
        # p[2] is COLUMN
        p[0].head = p[1].head
        if p[1].tail or p[2].head:
            pass  # FIXME: add warning, or handle space between point and name in SearchField ?
        # p[3] is the expression
        p[3].head = p[2].tail + p[3].head
        self.pos(p, head_transfer=True)


head_tail = HeadTailManager()
