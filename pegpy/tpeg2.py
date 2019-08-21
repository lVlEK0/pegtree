import sys
import os
import errno
import inspect
from collections import namedtuple
from enum import Enum
from pathlib import Path

# ParsingExpression

class ParsingExpression(object):
    def __iter__(self):  pass
    def __len__(self): return 0

    # operator overloading 
    def __and__(self, y): return Seq2(self, y)
    def __rand__(self, y): return Seq2(self, y)
    def __or__(self, y): return Ore2(self, y)
    def __truediv__(self, y): return Ore2(self, y)
    def __invert__(self): return Not(self)

class Char(ParsingExpression):
    __slots__ = ['text']

    def __init__(self, text):
        self.text = text


class Range(ParsingExpression):
    __slots__ = ['chars', 'ranges']

    def __init__(self, chars, ranges):
        self.chars = chars
        self.ranges = ranges


class Any(ParsingExpression):
    pass


class Ref(ParsingExpression):
    def __init__(self, name, peg):
        self.name = name
        self.peg = peg

    def uname(self):
        return self.name if self.name[0].isdigit() else self.peg.gid + self.name
    
    def deref(self):
        return self.peg[self.name]
    
    def get(self, key, value):
        return getattr(self, key) if hasattr(self, key) else value

    def set(self, key, value):
        setattr(self, key, value)


class Tuple(ParsingExpression):
    __slots__ = ['es']
    def __init__(self, *es):
        self.es = list(es)

    def __iter__(self):
        return iter(self.es)

    def __len__(self): 
        return len(self.es)


class Alt2(Tuple):
    pass


class Ore2(Tuple):
    pass


class Seq2(Tuple):
    pass


class Unary(ParsingExpression):
    __slot__ = ['e']

    def __init__(self, e):
        self.e = e

    def __iter__(self):
        yield self.e

    def __len__(self):
        return 1


class And(Unary):
    pass


class Not(Unary):
    pass


class Many(Unary):
    pass


class Many1(Unary):
    pass

class Option(Unary):
    pass


class Node(Unary):
    __slot__ = ['e', 'tag']

    def __init__(self, e, tag=''):
        self.e = e
        self.tag = tag


class Edge2(Unary):
    __slot__ = ['e', 'edge']

    def __init__(self, e, edge=''):
        self.e = e
        self.edge = edge


class Fold2(Unary):
    __slot__ = ['e', 'edge', 'tag']

    def __init__(self, e, edge='', tag=''):
        self.e = e
        self.edge = edge
        self.tag = tag


class Abs(Unary):
    __slot__ = ['e']

    def __init__(self, e):
        self.e = e

# Action


class Action(Unary):
    __slots__ = ['e', 'func', 'params']
    def __init__(self, e, func, params, pos4=None):
        self.e = e
        self.func = func
        self.params = params

# Action = namedtuple('Action', 'inner func params pos4')


# CONSTANT
EMPTY = Char('')
ANY = Any()
FAIL = Not(EMPTY)


# def setmethod():
#     def char1(x):
#         return Char(x) if x != '' else EMPTY

#     def seq2(x, y):
#         if isinstance(x, Empty):
#             return y
#         if isinstance(y, Empty):
#             return x
#         if isinstance(x, Char) and isinstance(y, Char):
#             return Char(x.text + y.text)
#         return Seq(x, y)

#     def alt2(x, y, c=Alt):
#         if isinstance(x, Char) and len(x.text) == 1:
#             if isinstance(y, Char) and len(y.text) == 1:
#                 return Range(x.text + y.text, ())
#             if isinstance(y, Range):
#                 return Range(x.text + y.chars, y.ranges)
#         if isinstance(x, Range):
#             if isinstance(y, Char) and len(y.text) == 1:
#                 return Range(x.chars + y.text, y.ranges)
#             if isinstance(y, Range):
#                 return Range(x.chars + y.chars, x.ranges + y.ranges)
#         return c(x, y)

#     def ore2(x, y):
#         if x is None or y is None:
#             return None
#         if x == EMPTY:
#             return EMPTY
#         return alt2(x, y, Ore)

#     def Xe(p):
#         if isinstance(p, str):
#             return char1(p)
#         if isinstance(p, dict):
#             for key in p:
#                 return Edge(key, Xe(p[key]))
#             return EMPTY
#         return p


def setup():
    def grouping(e, f):
        return '(' + repr(e) + ')' if f(e) else repr(e)

    def inUnary(e):
        return isinstance(e, Ore2) \
            or isinstance(e, Seq2) or isinstance(e, Alt2) \
            or (isinstance(e, Edge2))or isinstance(e, Fold2)

    CharTBL = str.maketrans(
        {'\n': '\\n', '\t': '\\t', '\r': '\\r', '\\': '\\\\', "'": "\\'"})

    RangeTBL = str.maketrans(
        {'\n': '\\n', '\t': '\\t', '\r': '\\r', '\\': '\\\\', ']': '\\]', '-': '\\-'})

    def rs(ranges):
        ss = tuple(map(lambda x: x[0].translate(
            RangeTBL) + '-' + x[1].translate(RangeTBL), ranges))
        return ''.join(ss)
    Char.__repr__ = lambda p: "'" + p.text.translate(CharTBL) + "'"
    Range.__repr__ = lambda p: "[" + \
        rs(p.ranges) + p.chars.translate(RangeTBL) + "]"
    Any.__repr__ = lambda p: '.'

    def ss(e): return grouping(e, lambda e: isinstance(
        e, Ore2)  or isinstance(e, Alt2))

    Seq2.__repr__ = lambda p: ' '.join(map(ss, p))
    Ore2.__repr__ = lambda p: ' / '.join(map(repr, p))
    # grouping(
    #     p.left, inUnary) + '?' if p.right == EMPTY else repr(p.left) + ' / ' + repr(p.right)
    Alt2.__repr__ = lambda p: ' | '.join(map(repr, p))
    #repr(p.left) + ' | ' + repr(p.right)

    And.__repr__ = lambda p: '&'+grouping(p.e, inUnary)
    Not.__repr__ = lambda p: '!'+grouping(p.e, inUnary)
    Many.__repr__ = lambda p: grouping(p.e, inUnary)+'*'
    Many1.__repr__ = lambda p: grouping(p.e, inUnary)+'+'
    Option.__repr__ = lambda p: grouping(p.e, inUnary)+'?'
    Ref.__repr__ = lambda p: p.name
    Node.__repr__ = lambda p: '{' + str(p.e) + ' #' + p.tag + '}'
    Edge2.__repr__ = lambda p: (
        '$' if p.edge == '' else p.edge + ': ') + grouping(p.e, inUnary)
    Fold2.__repr__ = lambda p: (
        '' if p.edge == '' else p.edge + ':') + '^ {' + str(p.e) + ' #' + p.tag + '}'
    Abs.__repr__ = lambda p: f'@abs({p.e})'
    Action.__repr__ = lambda p: f'@{p.func}{p.params}'

setup()

# # Grammar

GrammarId = 0


class Grammar(dict):
    def __init__(self):
        global GrammarId
        self.gid = str(GrammarId)
        GrammarId += 1
        self.N = []

    def __repr__(self):
        ss = []
        for rule in self.N:
            ss.append(rule)
            ss.append('=')
            ss.append(repr(self[rule]))
            ss.append('\n')
        return ''.join(ss)

    def add(self, key, item):
        if not key in self:
            self.N.append(key)
        self[key] = item

    def newRef(self, name):
        key = '@' + name
        if not key in self:
            super().__setitem__(key, Ref(name, self))
        return self[key]

    def start(self):
        if len(self.N) == 0:
            self['EMPTY'] = EMPTY
        return self.N[0]

##

# # TPEG Grammar Definition

def TPEG(g):
    def Xe(p):
        if isinstance(p, str):
            return Char(p)
        if isinstance(p, dict):
            for key in p:
                return Edge2(Xe(p[key]), key)
            return EMPTY
        return p

    def seq(*ps):
        if len(ps) == 0: return EMPTY
        if len(ps) == 1: return Xe(ps[0])
        return Seq2(*list(map(Xe, ps)))
    e = seq

    def choice(*ps):
        return Ore2(*list(map(Xe, ps)))

    def many(*ps): return Many(seq(*ps))
    def many1(*ps): return Many1(seq(*ps))
    def option(*ps): return Option(seq(*ps))
    def TreeAs(node, *ps): return Node(seq(*ps), node)
    def ListAs(*ps): return Node(seq(*ps), '')
    def FoldAs(edge, node, *ps): return Fold2(seq(*ps), edge, node)

    def c(*ps):
        chars = []
        ranges = []
        for x in ps:
            if isinstance(x, str):
                chars.append(x)
            else:
                ranges.append(tuple(x))
        return Range(''.join(chars), ranges)
    #
    def ref(p): return g.newRef(p)
    def rule(g, name, *ps): g.add(name,seq(*ps))

    __ = ref('__')
    _ = ref('_')
    EOS = ref('EOS')
    EOL = ref('EOL')
    S = ref('S')
    COMMENT = ref('COMMENT')
    Expression = ref('Expression')
    Identifier = ref('Identifier')
    Empty = ref('Empty')

    rule(g, 'Start', __, ref('Source'), ref('EOF'))

    rule(g, '__', many(choice(c(' \t\r\n'),COMMENT)))
    rule(g, '_', many(choice(c(' \t'),COMMENT)))

    rule(g, 'EOF', Not(ANY))
    rule(g, 'COMMENT', choice(
        e('/*', many(Not(e('*/')), ANY),'*/'), 
        e('//', many(Not(EOL), ANY))))
    rule(g, 'EOL', choice('\n', '\r\n', ref('EOF')))
    rule(g, 'S', c(' \t'))

    rule(g, 'Source', TreeAs('Source', many({'': ref('Statement')})))
    rule(g, 'EOS', _, many(choice(e(';', _), e(EOL,choice(S,COMMENT),_), EOL)))

    rule(g, 'Statement', choice(ref('Import'),ref('Example'),ref('Rule')))

    rule(g, 'Rule', TreeAs('Rule', {'name': Identifier}, __, '=', __, option(
        c('/|'), __), {'inner': Expression}, EOS))

    NAME = c(('A', 'Z'), ('a', 'z'), '@_') & many(
        c(('A', 'Z'), ('a', 'z'), ('0', '9'), '_.'))
    
    rule(g, 'Identifier', TreeAs('Name', NAME | e(
        '"', many(e(r'\"') | Not(c('\\"\n')) & ANY), '"')))

    # import
    FROM = option(_, 'import', S, _, {'names': ref('Names')})
    rule(g, 'Import', TreeAs('Import', 'from', S, _, {
                         'name': Identifier / ref('Char')}, FROM) & EOS)

    rule(g,'Example', TreeAs('Example', 'example', S, _, {
                          'names': ref('Names')}, {'doc': ref('Doc')}) & EOS)
    rule(g, 'Names', ListAs({'': Identifier}, _, many(
        c(',&'), _, {'': Identifier}, _)))
    
    DELIM = Xe("'''")
    DOC1 = TreeAs("Doc", many(Not(e(DELIM, EOL)), ANY))
    DOC2 = TreeAs("Doc", many(Not(c('\r\n')), ANY))
    rule(g,'Doc', e(DELIM, many(S), EOL, DOC1, DELIM) | DOC2)

    rule(g, 'Expression', ref('Choice'), option(
        FoldAs('left', 'Alt', many1(__, '|', _, {'right': Expression}))))

    rule(g, 'Choice', ref('Sequence'), option(
        FoldAs('left', 'Ore', many1(__, '/', _, {'right': ref('Choice')}))))

    SS = e(S, _, ~EOL) | e(many1(_, EOL), S, _)
    rule(g, 'Sequence', ref('Predicate'), option(
        FoldAs('left', 'Seq', SS, {'right': ref('Sequence')})   ))

    rule(g, 'Predicate', choice(ref('Not'),ref('And'),ref('Suffix')))

    rule(g, 'Not', TreeAs('Not', '!', {'inner': ref('Predicate')}))
    rule(g,'And', TreeAs('And', '&', {'inner': ref('Predicate')}))
    #g['Append'] = TreeAs('Append', '$', {'inner': ref('Term')})

    rule(g, 'Suffix', ref('Term'), choice(
        FoldAs('inner', 'Many', '*'),
        FoldAs('inner', 'Many1', '+'),
        FoldAs('inner', 'Option', '?'), EMPTY))

    rule(g, 'Term', choice(ref('Group'),ref('Char'),ref('Class'),ref('Any'),ref('Node'),
        ref('Fold'),ref('EdgeFold'),ref('Edge'),ref('Func'),ref('Identifier')))
    rule(g, 'Group', '(', __, choice(Expression,Empty), __, ')')

    rule(g, 'Empty', TreeAs('Empty', EMPTY))
    rule(g, 'Any', TreeAs('Any', '.'))
    rule(g, 'Char', "'", TreeAs('Char', many(
        e('\\', ANY) | Not(c("'\n")) & ANY)), "'")
    rule(g, 'Class', 
        '[', TreeAs('Class', many(e('\\', ANY) | e(Not(e("]")),ANY))), ']')

    Tag = e('{', __, option('#', {'node': ref('Identifier')}), __)
    ETag = e(option('#', {'node': ref('Identifier')}), __, '}')

    rule(g, 'Node', TreeAs('Node', Tag, {'inner': choice(Expression,Empty)}, __, ETag))
    rule(g, 'Fold', '^', _, TreeAs(
        'Fold', Tag, {'inner': choice(Expression,Empty)}, __, ETag))
    rule(g, 'Edge', TreeAs('Edge', {'edge': ref('EdgeName')}, ':', _, {
                       'inner': ref('Term')}))
    rule(g, 'EdgeFold', TreeAs('Fold', {'edge': ref('EdgeName')}, ':', _, '^', _, Tag, {
                           'inner': choice(Expression,Empty)}, __, ETag))
    rule(g, 'EdgeName', TreeAs('', c(('a', 'z'), '$'), many(
        c(('A', 'Z'), ('a', 'z'), ('0', '9'), '_'))))
    rule(g, 'Func', TreeAs('Func', '@', {'name': Identifier}, '(', __, {
                       'params': ref('Params')}, ')'))
    rule(g, 'Params', ListAs({'': Expression}, many(
        _, ',', __, {'': Expression}), __))
    # rule(g, 'Ref', TreeAs('Ref', ref('REF')))
    # rule(g, 'REF', e('"', many(Xe('\\"') | e(Not(c('\\"\n')), ANY)), '"') | many1(
    #     Not(c(' \t\r\n(,){};<>[|/*+?=^\'`#')) & ANY))
    #g.N = ['Start', 'Sequence']
    return g


TPEGGrammar = TPEG(Grammar())
print(TPEGGrammar)

######################################################################
# ast.env

Pos4 = namedtuple('Pos4', 'urn inputs spos epos')


def bytestr(b):
    return b.decode('utf-8') if isinstance(b, bytes) else b


def decpos(urn, inputs, spos, epos):
    inputs = inputs[:spos + (1 if len(inputs) > spos else 0)]
    raws = inputs.split(b'\n' if isinstance(inputs, bytes) else '\n')
    return urn, spos, len(raws), len(raws[-1])-1


def decpos4(pos4):
    urn, inputs, spos, epos = pos4
    #urn, inputs, pos, length = decsrc(s)
    lines = inputs.split(b'\n' if isinstance(inputs, bytes) else '\n')
    linenum = 0
    cols = spos
    for line in lines:
        len0 = len(line) + 1
        linenum += 1
        if cols < len0:
            cols -= 1
            break
        cols -= len0
    epos = cols + (epos - spos)
    length = len(line) - cols if len(line) < epos else epos - cols
    if length <= 0:
        length = 1
    mark = []
    for i in range(cols):
        c = line[i]
        if c != '\t' and c != '　':
            c = ' '
        mark.append(c)
    mark = ''.join(mark) + ('^' * length)
    return (urn, spos, linenum, cols, bytestr(line), mark)


def serror4(pos4, msg='SyntaxError'):
    if pos4 is not None:
        urn, pos, linenum, cols, line, mark = decpos4(pos4)
        return '{} ({}:{}:{}+{})\n{}\n{}'.format(msg, urn, linenum, cols, pos, line, mark)
    return '{} (unknown source)'.format(msg)


class Logger(object):
    __slots__ = ['file', 'istty', 'isVerbose']

    def __init__(self, file=None, isVerbose=True):
        if file is None:
            self.file = sys.stdout
            self.istty = True
        else:
            self.file = open(file, 'w+')
            self.istty = False
        self.isVerbose = isVerbose

    def print(self, *args):
        file = self.file
        if len(args) > 0:
            file.write(str(args[0]))
            for a in args[1:]:
                file.write(' ')
                file.write(str(a))

    def println(self, *args):
        self.print(*args)
        self.file.write(os.linesep)
        self.file.flush()

    def dump(self, o, indent=''):
        if hasattr(o, 'dump'):
            o.dump(self, indent)
        else:
            self.println(o)

    def verbose(self, *args):
        if self.isVerbose:
            ss = map(lambda s: self.c('Blue', s), args)
            self.println(*ss)

    def bold(self, s):
        return '\033[1m' + str(s) + '\033[0m' if self.istty else str(s)

    COLOR = {
        "Black": '0;30', "DarkGray": '1;30',
        "Red": '0;31', "LightRed": '1;31',
        "Green": '0;32', "LightGreen": '1;32',
        "Orange": '0;33', "Yellow": '1;33',
        "Blue": '0;34', "LightBlue": '1;34',
        "Purple": '0;35', "LightPurple": '1;35',
        "Cyan": '0;36', "LightCyan": '1;36',
        "LightGray": '0;37', "White": '1;37',
    }

    def c(self, color, s):
        return '\033[{}m{}\033[0m'.format(Logger.COLOR[color], str(s)) + '' if self.istty else str(s)

    def perror(self, pos4, msg='Syntax Error'):
        self.println(serror4(pos4, self.c('Red', '[error] ' + str(msg))))

    def warning(self, pos4, msg):
        self.println(serror4(pos4, self.c('Orange', '[warning] ' + str(msg))))

    def notice(self, pos4, msg):
        self.println(serror4(pos4, self.c('Cyan', '[notice] ' + str(msg))))


STDLOG = Logger()

#####################################


def Merge(prev, edge, child):
    return (prev, edge, child)


class ParseTree(object):
    __slots__ = ['tag', 'urn', 'inputs', 'spos', 'epos', 'child']

    def __init__(self, tag, urn, inputs, spos, epos, child):
        self.tag = tag
        self.urn = urn
        self.inputs = inputs
        self.spos = spos
        self.epos = epos
        self.child = child

    def __eq__(self, tag):
        return self.tag == tag

    def subs(self):
        if not isinstance(self.child, list):
            stack = []
            cur = self.child
            while cur is not None:
                prev, edge, child = cur
                if child is not None:
                    stack.append((edge, child))
                cur = prev
            self.child = list(stack[::-1])
        return self.child

    def __len__(self):
        return len(self.subs())

    def __contains__(self, label):
        for edge, _ in self.subs():
            if label == edge: return True
        return False

    def __getitem__(self, label):
        if isinstance(label, int):
            return self.subs()[label][1]
        for edge, child in self.subs():
            if label == edge:
                return child
        return None

    def get(self, label: str, default=None, conv=lambda x: x):
        for edge, child in self.subs():
            if label == edge:
                return conv(child)
        return default

    def getString(self, label: str, default=None):
        return self.get(label, default, str)

    def keys(self):
        ks = []
        for edge, _ in self.subs():
            if edge != '': ks.append(edge)
        return ks

    def __iter__(self):
        return map(lambda x: x[1], self.subs())

    def __str__(self):
        s = self.inputs[self.spos:self.epos]
        return s.decode('utf-8') if isinstance(s, bytes) else s

    def __repr__(self):
        sb = []
        self.strOut(sb)
        return "".join(sb)

    def strOut(self, sb):
        sb.append("[#")
        sb.append(self.tag)
        c = len(sb)
        for tag, child in self.subs():
            sb.append(' ' if tag == '' else ' ' + tag + '=')
            child.strOut(sb)
        if c == len(sb):
            s = self.inputs[self.spos:self.epos]
            if isinstance(s, str):
                sb.append(" '")
                sb.append(s)
                sb.append("'")
            elif isinstance(s, bytes):
                sb.append(" '")
                sb.append(s.decode('utf-8'))
                sb.append("'")
            else:
                sb.append(" ")
                sb.append(str(s))
        sb.append("]")

    def pos(self):
        return decpos(self.urn, self.inputs, self.spos, self.epos)

    def getpos4(self):
        return Pos4(self.urn, self.inputs, self.spos, self.epos)

    def dump(self, w, indent=''):
        if self.child is None:
            s = self.inputs[self.spos:self.epos]
            w.println(w.bold("[#" + self.tag), repr(s) + w.bold("]"))
            return
        w.println(w.bold("[#" + self.tag))
        indent2 = '  ' + indent
        for tag, child in self:
            w.print(indent2 if tag is '' else indent2 + tag + '=')
            child.dump(w, indent2)
        w.println(indent + w.bold("]"))

# TreeConv

class ParseTreeConv(object):
    def settree(self, s, t):
        if hasattr(s, 'pos3'):
            s.pos3 = t.pos3()
        return s

    def conv(self, t: ParseTree, logger):
        tag = t.tag
        if hasattr(self, tag):
            f = getattr(self, tag)
            return self.settree(f(t, logger), t)
        return t

######################################################################


class ParserContext:
    __slots__ = ['urn', 'inputs', 'pos', 'epos',
                 'headpos', 'ast', 'state', 'memo']

    def __init__(self, urn, inputs, spos, epos):
        self.urn = urn
        self.inputs = inputs
        self.pos = spos
        self.epos = epos
        self.headpos = spos
        self.ast = None
        self.state = None
        self.memo = {}

    # setup parser


def setup_generate():
    def gen_Pexp(pe, **option):
        try:
            return pe.gen(**option)
        except AttributeError:
            print('@AttributeError', pe)
            return pe.gen(**option)

    # def gen_Empty(pe, **option):
    #     def empty(px): return True
    #     return empty

    def gen_Char(pe, **option):
        chars = pe.text
        clen = len(pe.text)

        def match_char(px):
            if px.inputs.startswith(chars, px.pos):
                px.pos += clen
                return True
            return False

        return match_char

    # Range

    def first_range(pe):
        cs = 0
        for c in pe.chars:
            cs |= 1 << ord(c)
        for r in pe.ranges:
            for c in range(ord(r[0]), ord(r[1])+1):
                cs |= 1 << c
        return cs

    def gen_Range(pe, **option):
        #offset = pe.min()
        bitset = first_range(pe)  # >> offset

        def bitmatch(px):
            if px.pos < px.epos:
                shift = ord(px.inputs[px.pos])  # - offset
                if shift >= 0 and (bitset & (1 << shift)) != 0:
                    px.pos += 1
                    return True
            return False

        return bitmatch

    # Any

    def gen_Any(pe, **option):
        def match_any(px):
            if px.pos < px.epos:
                px.pos += 1
                return True
            return False

        return match_any

    # And

    def gen_And(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def match_and(px):
            pos = px.pos
            if pf(px):
                # backtracking
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                return True
            return False

        return match_and

    # Not

    def gen_Not(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def match_not(px):
            pos = px.pos
            ast = px.ast
            if not pf(px):
                # backtracking
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                px.ast = ast
                return True
            return False

        return match_not

    # Many

    def gen_Many(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def match_many(px):
            pos = px.pos
            ast = px.ast
            while pf(px) and pos < px.pos:
                pos = px.pos
                ast = px.ast
            px.headpos = max(px.pos, px.headpos)
            px.pos = pos
            px.ast = ast
            return True

        return match_many

    def gen_Many1(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def match_many1(px):
            if pf(px):
                pos = px.pos
                ast = px.ast
                while pf(px) and pos < px.pos:
                    pos = px.pos
                    ast = px.ast
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                px.ast = ast
                return True
            return False

        return match_many1

    def gen_Option(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def match_option(px):
            pos = px.pos
            ast = px.ast
            if not pf(px):
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                px.ast = ast
            return True
        return match_option

    # Seq

    def gen_Seq(pe, **option):
        pfs = tuple(map(lambda e: gen_Pexp(e, **option), pe))

        def match_seq(px):
            for pf in pfs:
                if not pf(px):
                    return False
            return True
        return match_seq

    # Ore

    def gen_Ore(pe, **option):
        pfs = tuple(map(lambda e: gen_Pexp(e, **option), pe))

        def match_ore(px):
            pos = px.pos
            ast = px.ast
            for pf in pfs:
                if pf(px):
                    return True
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                px.ast = ast
            return False

        return match_ore

    # Ref

    def gen_Ref(ref, **option):
        key = ref.uname()
        generated = option['generated']
        if not key in generated:
            generated[key] = lambda px: generated[key](px)
            generated[key] = gen_Pexp(ref.deref(), **option)
            #memo[key] = emit_trace(ref, emit(ref.deref()))
        return generated[key]

    # Tree Construction

    def gen_Node(pe, **option):
        node = pe.tag
        pf = gen_Pexp(pe.e, **option)
        mtree = option.get('tree', ParseTree)

        def tree(px):
            pos = px.pos
            px.ast = None
            if pf(px):
                px.ast = mtree(node, px.urn, px.inputs, pos, px.pos, px.ast)
                return True
            return False

        return tree

    def gen_Edge(pe, **option):
        edge = pe.edge
        pf = gen_Pexp(pe.e, **option)
        merge = option.get('merge', Merge)

        def fedge(px):
            prev = px.ast
            if pf(px):
                px.ast = merge(prev, edge, px.ast)
                return True
            return False
        return fedge

    def gen_Fold(pe, **option):
        edge = pe.edge
        node = pe.tag
        pf = gen_Pexp(pe.e, **option)
        mtree = option.get('tree', ParseTree)
        merge = option.get('merge', Merge)

        def fold(px):
            pos = px.pos
            px.ast = merge(None, edge, px.ast)
            if pf(px):
                px.ast = mtree(node, px.urn, px.inputs, pos, px.pos, px.ast)
                return True
            return False

        return fold

    def gen_Abs(pe, **option):
        pf = gen_Pexp(pe.e, **option)

        def unit(px):
            ast = px.ast
            if pf(px):
                px.ast = ast
                return True
            return False

        return unit

    # StateTable

    State = namedtuple('State', 'sid val prev')

    SIDs = {}

    def getsid(name):
        if not name in SIDs:
            SIDs[name] = len(SIDs)
        return SIDs[name]

    def getstate(state, sid):
        while state is not None:
            if state.sid == sid:
                return state
            state = state.prev
        return None

    # def adddict(px, s):
    #     if len(s) == 0:
    #         return
    #     key = s[0]
    #     if key in px.memo:
    #         l = px.memo[key]
    #         slen = len(s)
    #         for i in range(len(l)):
    #             if slen > len(l[i]):
    #                 l.insert(i, s)
    #                 return
    #         l.append(s)
    #     else:
    #         px.memo[key] = [s]

    def gen_Action(pe, **option):
        fname = pe.func
        params = pe.params

        if fname == 'lazy':  # @lazy(A)
            name = pe.e.name
            peg = option.get('peg')
            return gen_Pexp(peg.newRef(name), **option) if name in peg else gen_Pexp(pe.e, **option)

        if fname == 'skip':  # @recovery({..})
            def skip(px):
                px.pos = px.headpos
                return px.pos < px.epos
            return skip

        # SPEG
        if fname == 'symbol':   # @symbol(A)
            sid = getsid(str(params[0]))
            pf = gen_Pexp(pe.e, **option)

            def symbol(px):
                pos = px.pos
                if pf(px):
                    px.state = State(sid, px.inputs[pos:px.pos], px.state)
                    return True
                return False
            return symbol

        if fname == 'exists':   # @exists(A)
            sid = getsid(str(params[0]))
            return lambda px: getstate(px.state, sid) != None

        if fname == 'match':   # @match(A)
            sid = getsid(str(params[0]))

            def match(px):
                state = getstate(px.state, sid)
                if state is not None and px.inputs.startswith(state.val, px.pos):
                    px.pos += len(state.val)
                    return True
                return False
            return match

        if fname == 'scope':  # @scope(e)
            pf = gen_Pexp(pe.e, **option)

            def scope(px):
                state = px.state
                res = pf(px)
                px.state = state
                return res
            return scope

        if fname == 'on':  # @on(!A, e)
            name = str(params[0])
            pf = gen_Pexp(pe.e, **option)
            if name.startswith('!'):
                sid = getsid(name[1:])

                def off(px):
                    state = px.state
                    px.state = State(sid, False, px.state)
                    res = pf(px)
                    px.state = state
                    return res
                return off

            else:
                sid = getsid(name[1:])

                def on(px):
                    state = px.state
                    px.state = State(sid, False, px.state)
                    res = pf(px)
                    px.state = state
                    return res
                return on

        if fname == 'if':  # @if(A)
            sid = getsid(str(params[0]))

            def cond(px):
                state = getstate(px.state, sid)
                return state != None and state.val
            return cond

        if fname == 'def':  # @def(NAME)
            name = str(params[0])
            pf = gen_Pexp(pe.e, **option)

            def defdict(px):
                pos = px.pos
                if pf(px):
                    s = px.inputs[pos:px.pos]
                    if len(s) == 0:
                        return True
                    if name in px.memo:
                        d = px.memo[name]
                    else:
                        d = {}
                        px.memo[name] = d
                    key = s[0]
                    if not key in d:
                        d[key] = [s]
                        return True
                    l = d[key]
                    slen = len(s)
                    for i in range(len(l)):
                        if slen > len(l[i]):
                            l.insert(i, s)
                            break
                    return True
                return False
            return defdict

        if fname == 'in':  # @in(NAME)
            name = str(params[0])

            def refdict(px):
                if name in px.memo and px.pos < px.epos:
                    d = px.memo[name]
                    key = px.inputs[px.pos]
                    if key in d:
                        for s in d[key]:
                            if px.inputs.startswith(s, px.pos):
                                px.pos += len(s)
                                return True
                return False
            return refdict

        print('@TODO: gen_Action', pe.func)
        return gen_Pexp(pe.e, **option)

    #Empty.gen = gen_Empty
    Char.gen = gen_Char
    Range.gen = gen_Range
    Any.gen = gen_Any

    And.gen = gen_And
    Not.gen = gen_Not
    Many.gen = gen_Many
    Many1.gen = gen_Many1
    Option.gen = gen_Option

    Seq2.gen = gen_Seq
    Ore2.gen = gen_Ore
    Alt2.gen = gen_Ore
    Ref.gen = gen_Ref

    Node.gen = gen_Node
    Edge2.gen = gen_Edge
    Fold2.gen = gen_Fold
    Abs.gen = gen_Abs

    Action.gen = gen_Action

    def generate(peg, **option):
        name = option.get('start', peg.start())
        p = peg.newRef(name)
        option['peg'] = peg
        option['generated'] = {}

        pf = gen_Pexp(p, **option)
        mtree = option.get('tree', ParseTree)
        conv = option.get('conv', lambda x: x)

        def parse(inputs, urn='(unknown)', pos=0, epos=None):
            if epos is None:
                epos = len(inputs)
            px = ParserContext(urn, inputs, pos, epos)
            pos = px.pos
            result = None
            if not pf(px):
                result = mtree("err", urn, inputs, px.headpos, epos, None)
            else:
                result = px.ast if px.ast is not None else mtree(
                    "", urn, inputs, pos, px.pos, None)
            return conv(result)

        return parse
    return generate


generate = setup_generate()

# ######################################################################

## TreeState

class T(Enum):
    Unit = 0
    Tree = 1
    Mut = 2
    Fold = 3

def nameTreeState(n):
    loc = n.rfind('.')
    n = n[loc+1:] if loc > 0 else n
    c = n[0]
    if c.islower():
        if n.replace('_','').islower() : return T.Mut
    if c.isupper():
        for c in n:
            if c.islower():
                return T.Tree
    return T.Unit

# isAlwaysConsumed
def setup2():

    def defmethod(name, f, cs=[
        Char, Range, Any, Seq2, Ore2, Alt2, And, Not, Many, Many1, Ref,
        Node, Edge2, Fold2, Abs, Action]):
        for c in cs: setattr(c, name, f)

    defmethod('isAlwaysConsumed', lambda p: len(p.text) > 0, [Char])
    defmethod('isAlwaysConsumed', lambda p: True, [Any, Range])
    defmethod('isAlwaysConsumed', lambda p: False, [Many, Not, And, Option])
    defmethod('isAlwaysConsumed',
            lambda p: p.e.isAlwaysConsumed(),
            [Many1, Edge2, Node, Fold2, Abs, Action])

    def checkSeq(p):
        for e in p:
            if e.isAlwaysConsumed(): return True
        return False
    Seq2.isAlwaysConsumed = checkSeq

    def checkOre(p):
        for e in p:
            if not e.isAlwaysConsumed():
                return False
        return True
    Ore2.isAlwaysConsumed = checkOre
    Alt2.isAlwaysConsumed = checkOre

    def checkRef(p):
        memoed = p.get('isAlwaysConsumed', None)
        if memoed == None:
            p.isAlwaysConsumed= True
            memoed = (p.deref()).isAlwaysConsumed()
            p.isAlwaysConsumed = memoed
        return memoed
    Ref.isAlwaysConsumed = checkRef

    # treeState
    def treeState(e):
        return e.treeState()

    defmethod('treeState', lambda p: T.Unit, [Char, Any, Range, Not, Abs])
    defmethod('treeState', lambda p: T.Tree, [Node] )
    defmethod('treeState', lambda p: T.Mut,  [Edge2] )
    defmethod('treeState', lambda p: T.Fold, [Fold2] )

    def mutTree(ts): return T.Mut if ts == T.Tree else ts
    defmethod('treeState', lambda p: mutTree(treeState(p.e)), [Many, Many1, Option, And])
    defmethod('treeState', lambda p: treeState(p.e), [Action])

    # def treeRef(pe):
    #     ts = pe.get('ts', None)
    #     if ts is None:
    #         pe.ts = T.Unit
    #         pe.ts = pe.deref().treeState()
    #         return pe.ts
    #     return ts
    Ref.treeState = lambda p : nameTreeState(p.name)

    def treeSeq(pe):
        ts = T.Unit
        for se in pe:
            ts = se.treeState()
            if ts != T.Unit: return ts
        return ts
    Seq2.treeState = treeSeq

    def treeAlt(pe):
        ts = list(map(treeState, pe))
        if T.Tree in ts:
            return T.Tree if ts.count(T.Tree) == len(ts) else T.Mut
        if T.Fold in ts:
            return T.Fold
        return T.Mut if T.Mut in ts else T.Unit
    Alt2.treeState = treeAlt
    Ore2.treeState = treeAlt

    def formTree(e, state):
        e, _ = e.formTree(state)
        return e

    def formTree2(e, state):
        return e.formTree(state)
    
    def formNode(pe: Node, state):
        if state == T.Unit:  # {e #T} => e
            return formTree(pe.e, state), T.Unit
        if state == T.Fold:  # {e #T} => ^{e #T}
            return Fold2(formTree(pe.e, T.Mut), '', pe.tag), T.Fold
        pe = Node(formTree(pe.e, T.Mut), pe.tag)
        if state == T.Mut:  # {e #T} => : {e #T}
            return Edge2(pe, ''), state
        return pe, T.Fold   # state == T.Tree
    Node.formTree = formNode

    def formEdge(pe: Edge2, state):
        if state == T.Unit:  # L: e  => e
            return formTree(pe.e, state), T.Unit
        if state == T.Fold: # L: e => L:^ {e}
            return Fold2(formTree(pe.e, T.Mut), pe.edge, ''), T.Fold
        sub, ts2 = formTree2(pe.e, T.Tree)
        if ts2 != T.Fold:  
            sub = Node(sub, '')  # L:e => L: {e}
        pe = Edge2(sub, pe.edge)
        return (Node(pe, ''), T.Fold)  if state == T.Tree else (pe, T.Mut)
    Edge2.formTree = formEdge

    def formFold(pe: Fold2, state):
        if state == T.Unit:  # ^{e #T} => e
            return formTree(pe.e, state), T.Unit
        if state == T.Mut: # L:^ {e #T} => L:{ e #T}
            return Edge2(Node(formTree(pe.e, T.Mut), pe.tag), pe.edge), T.Mut
        if state == T.Tree: # L:^ {e #T} => {e #T}
            return Node(formTree(pe.e, T.Mut), pe.tag), T.Fold
        return Fold2(formTree(pe.e, T.Mut), pe.edge, pe.tag), T.Fold
    Fold2.formTree = formFold

    def formRef(pe, state):
        refstate = pe.treeState()
        if state == T.Unit:
            if refstate == T.Unit: # original
                return pe, T.Unit
            else:
                return Abs(pe), T.Unit
        if state == T.Tree:
            if refstate == T.Tree: # original
                return pe, T.Fold
            if refstate == T.Mut:  # mut => { mut }
                return Node(pe, ''), T.Fold
            return pe, state  # no change
        if state == T.Mut:
            if refstate == T.Unit or refstate == T.Mut:
                return pe, T.Mut
            assert refstate == T.Tree  # Expr => L: Expr
            return Edge2(pe, ''), T.Mut
        if state == T.Fold:
            if refstate == T.Unit:
                return pe, T.Fold
            if refstate == T.Tree:  # Expr => ^{ Expr }
                return Fold2(Edge2(pe, ''), '', ''), T.Fold
            if refstate == T.Mut:  # expr => ^{ expr }
                return Fold2(pe, '', ''), T.Fold
        assert(pe == None)  # Never happen
    Ref.formTree = formRef

    def formSeq(pe, state):
        for i, e in enumerate(pe):
            pe.es[i], state = formTree2(e, state)
        return pe, state
    Seq2.formTree = formSeq

    def formAlt(pe, state):
        for i, e in enumerate(pe):
            pe.es[i],nextstate = formTree2(e, state)
        return pe, nextstate
    Alt2.formTree = formAlt
    Ore2.formTree = formAlt

    def formUnary(pe, state):
        pe.e, state = formTree2(pe.e, state)
        return pe, state
    Unary.formTree = formUnary

    def formTerm(pe, state):
        return pe, state
    ParsingExpression.formTree = formTerm

setup2()

def grammar_factory():
    def char1(x):
        return Char(x) if x != '' else EMPTY

    def unquote(s):
        if s.startswith('\\'):
            if s.startswith('\\n'):
                return '\n', s[2:]
            if s.startswith('\\t'):
                return '\t', s[2:]
            if s.startswith('\\r'):
                return '\r', s[2:]
            if s.startswith('\\v'):
                return '\v', s[2:]
            if s.startswith('\\f'):
                return '\f', s[2:]
            if s.startswith('\\b'):
                return '\b', s[2:]
            if (s.startswith('\\x') or s.startswith('\\X')) and len(s) > 4:
                c = int(s[2:4], 16)
                return chr(c), s[4:]
            if (s.startswith('\\u') or s.startswith('\\U')) and len(s) > 6:
                c = int(s[2:6], 16)
                return chr(c), s[6:]
            else:
                return s[1], s[2:]
        else:
            return s[0], s[1:]

    class PEGConv(ParseTreeConv):
        def __init__(self, peg):
            self.peg = peg

        def Empty(self, t, logger):
            return EMPTY

        def Any(self, t, logger):
            return ANY

        def Char(self, t, logger):
            s = str(t)
            sb = []
            while len(s) > 0:
                c, s = unquote(s)
                sb.append(c)
            return char1(''.join(sb))

        def Class(self, t, logger):
            s = str(t)
            chars = []
            ranges = []
            while len(s) > 0:
                c, s = unquote(s)
                if s.startswith('-') and len(s) > 1:
                    c2, s = unquote(s[1:])
                    ranges.append((c, c2))
                else:
                    chars.append(c)
            return Range(''.join(chars), ranges)

        def Ref(self, t, logger):
            name = str(t)
            if name in self.peg:
                return Action(self.peg.newRef(name), 'NT', (name,), t.getpos4())
            if name[0].isupper() or name[0].islower() or name.startswith('_'):
                logger.warning(t.getpos4(), f'undefined nonterminal {name}')
                #self.peg.add(name, FAIL)
                # return self.peg.newRef(name)
            return char1(name[1:-1]) if name.startswith('"') else char1(name)

        def Many(self, t, logger):
            return Many(self.conv(t['inner'], logger))

        def Many1(self, t, logger):
            return Many1(self.conv(t['inner'], logger))

        def Option(self, t, logger):
            return Option(self.conv(t['inner'], logger))

        def And(self, t, logger):
            return And(self.conv(t['inner'], logger))

        def Not(self, t, logger):
            return Not(self.conv(t['inner'], logger))

        def Seq(self, t, logger):
            return Seq2(*tuple(map(lambda p: self.conv(p, logger), t)))
            # return self.conv(t['left'], logger) & self.conv(t['right'], logger)

        def Ore(self, t, logger):
            return Ore2(*tuple(map(lambda p: self.conv(p, logger), t)))
            # return self.conv(t['left'], logger) / self.conv(t['right'], logger)

        def Alt(self, t, logger):
            return Alt2(*tuple(map(lambda p: self.conv(p, logger), t)))
            # return self.conv(t['left'], logger) // self.conv(t['right'], logger)

        def Node(self, t, logger):
            node = t.getString('node', '')
            inner = self.conv(t['inner'], logger)
            return Node(inner, node)

        def Edge(self, t, logger):
            edge = t.getString('edge', '')
            inner = self.conv(t['inner'], logger)
            return Edge2(inner, edge)

        def Fold(self, t, logger):
            edge = t.getString('edge', '')
            node = t.getString('node', '')
            inner = self.conv(t['inner'], logger)
            return Fold2(inner, edge, node)

        def Append(self, t, logger):
            name = ''
            tsub = t['inner']
            if tsub == 'Func':
                a = tsub.asArray()
                name = str(a[0])
                inner = self.conv(a[1], logger)
            else:
                inner = self.conv(tsub, logger)
            return Edge2(inner, name)

        FIRST = {'lazy', 'scope', 'symbol', 'match', 'equals', 'contains'}

        def Func(self, t, logger):
            funcname = t.getString('name', '')
            ps = []
            for _, p in t['params']:
                ps.append(self.conv(p, logger))
            if funcname in PEGConv.FIRST:
                return Action(ps[0], funcname, tuple(ps), t['name'].getpos4())
            return Action(EMPTY, funcname, tuple(ps), t['name'].getpos4())

    def example(peg, name, doc):
        peg['@@example'].append((name, doc))

    def checkRec(pe, consumed, peg, name, visited, logger):
        if isinstance(pe, ParseTree):
            nt = str(pe)
            if nt == name and not consumed:
                logger.warning(pe.getpos4(), f'left recursion {nt}')
                return FAIL
            if nt not in peg:
                logger.warning(pe.getpos4(), f'undefined nonterminal {nt}')
                return char1(nt[1:-1]) if nt.startswith('"') else char1(nt)
            pe = peg.newRef(nt)
        if isinstance(pe, Ref):
            if peg == pe.peg and pe.name not in visited:
                visited[pe.name] = True
                checkRec(peg[pe.name], consumed, peg, name, visited, logger)
            return pe
        if isinstance(pe, Unary):
            pe.e = checkRec(pe.e, consumed, peg, name, visited, logger)
            return pe
        if isinstance(pe, Seq2):
            for i, e in enumerate(pe):
                pe.es[i] = checkRec(e, consumed, peg, name, visited, logger)
                consumed = (pe.es[i]).isAlwaysConsumed()
            return pe
        if isinstance(pe, Tuple):
            for i, e in enumerate(pe):
                pe.es[i] = checkRec(e, consumed, peg, name, visited, logger)
            return pe
        return pe
    
    pegparser = generate(TPEGGrammar)

    def load_grammar(g, file, logger):
        if '@@example' not in g:
            g['@@example'] = []
        if isinstance(file, Path):
            f = file.open()
            data = f.read()
            f.close()
            t = pegparser(data, file)
            basepath = str(file)
        else:
            basepath = inspect.currentframe().f_back.f_code.co_filename
            t = pegparser(file, basepath)
            basepath = (str(Path(basepath).resolve().parent))
        if t == 'err':
            logger.perror(t.getpos4())
            return
        # load
        for stmt in t:
            if stmt == 'Rule':
                name = str(stmt['name'])
                pos4 = stmt['name'].getpos4()
                if name in g:
                    logger.perror(pos4, f'redefined name {name}')
                    continue
                g.add(name, stmt['inner'])
                g.newRef(name).pos = pos4
            elif stmt == 'Example':
                doc = stmt['doc']
                for n in stmt['names']:
                    example(g, str(n), doc.getpos4())
            elif stmt == 'Import':
                urn = str(stmt['name'])
                lg = grammar(urn, basepath, logger)
                for n in stmt['names']:
                    lname = str(n)  # ns.Expression
                    name = lname
                    if lname.find('.') != -1:
                        name = lname.split('.')[-1]
                    pos4 = n.getpos4()
                    if not name in lg:
                        logger.perror(pos4, f'undefined name {name}')
                        continue
                    g.add(lname, Action(lg.newRef(name),
                                        'import', (name, urn), pos4))
        pconv = PEGConv(g)
        for name in g.N[:]:
            t = g[name]
            if isinstance(t, ParseTree):
                g[name] = pconv.conv(t, logger)
        for name in g.N: # FIXME
            g[name] = checkRec(g[name], False, g, name, {}, logger)
        for name in g.N: 
            pe = g[name]
            ts = pe.treeState()
            ts2 = nameTreeState(name)
            if ts != ts2:
                print('(@NAME)', ts, ts2)
            pe2,_ = pe.formTree(ts)
            if str(pe) != str(pe2):
                print('(@OLD)', ts, name, '=', pe)
                print('(@NEW)', ts, name, '=', pe2)
            g[name] = pe2
        #end of load_grammar()

    def findpath(paths, file):
        if file.find('=') > 0:
            return file
        for p in paths:
            path = Path(p) / file
            #print('@', path)
            if path.exists():
                return path.resolve()
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file)

    GrammarDB = {}

    def grammar(urn, basepath='', logger=STDLOG):
        paths = []
        if basepath == '':
            paths.append('')
        else:
            paths.append(str(Path(basepath).resolve().parent))
        framepath = inspect.currentframe().f_back.f_code.co_filename
        paths.append(str(Path(framepath).resolve().parent))
        paths.append(str(Path(__file__).resolve().parent / 'grammar'))
        paths += os.environ.get('GRAMMAR', '').split(':')
        path = findpath(paths, urn)
        key = str(path)
        if key in GrammarDB:
            return GrammarDB[key]
        peg = Grammar()
        load_grammar(peg, path, logger)
        GrammarDB[key] = peg
        return peg

    return grammar


grammar = grammar_factory()


if __name__ == '__main__':
    peg = grammar('math.tpeg')
    print(peg)