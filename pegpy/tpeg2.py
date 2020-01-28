import sys
import os
import errno
import inspect
from collections import namedtuple
from enum import Enum
from pathlib import Path

def DEBUG(*x):
    if 'DEBUG' in os.environ:
        print('@DEBUG', *x)

# ParsingExpression

class ParsingExpression(object):
    def __iter__(self): pass
    def __len__(self): return 0


class Any(ParsingExpression):
    def __repr__(self):
        return '.'

    def minLen(self): return 1

class Char(ParsingExpression):
    __slots__ = ['text']

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return "'" + self.text.translate(CharTBL) + "'"

    def minLen(self): return len(self.text)

class Range(ParsingExpression):
    __slots__ = ['chars', 'ranges']

    def __init__(self, chars, ranges):
        self.chars = chars
        self.ranges = ranges

    def __repr__(self):
        return "[" + rs(self.ranges) + self.chars.translate(RangeTBL) + "]"

    def minLen(self): return 1


def unique_range(chars, ranges):
    cs = 0
    for c in chars:
        cs |= 1 << ord(c)
    if isinstance(ranges, str):
        r = []
        while len(ranges) > 1:
            r.append(ranges[0:2])
            ranges = ranges[2:]
        ranges = tuple(r)
    for r in ranges:
        for c in range(ord(r[0]), ord(r[1])+1):
            cs |= 1 << c
    return cs

class Ref(ParsingExpression):
    def __init__(self, peg, name):
        self.peg = peg
        self.name = name

    def __repr__(self):
        return self.name

    def uname(self):
        return self.name if self.name[0].isdigit() else self.peg.gid + self.name

    def deref(self):
        return self.peg[self.name]

    def minLen(self): 
        if not hasattr(self, 'minlen'):
            self.minlen = 0
            self.minlen = self.deref().minLen()
        return self.minlen

    # def get(self, key, value):
    #     return getattr(self, key) if hasattr(self, key) else value

    # def set(self, key, value):
    #     setattr(self, key, value)


class Tuple(ParsingExpression):
    __slots__ = ['es']

    def __init__(self, *es):
        self.es = list(es)

    def __iter__(self):
        return iter(self.es)

    def __len__(self):
        return len(self.es)

    def minLen(self):
        if not hasattr(self, 'minlen'):
            self.minlen = min(map(lambda e: e.minLen(), self.es))
        return self.minlen

class Seq(Tuple):
    @classmethod
    def new(cls, *es):
        ls = [es[0]]
        for e in es[1:]:
            if e == EMPTY: continue
            if isinstance(e, Char) and isinstance(ls[-1], Char):
                ls[-1] = Char(ls[-1].text+e.text)
                continue
            ls.append(e)
        return ls[0] if len(ls) == 1 else Seq(*ls)

    def __repr__(self):
        return ' '.join(map(ss, self))

    def minLen(self):
        if not hasattr(self, 'minlen'):
            self.minlen = sum(map(lambda e: e.minLen(), self.es))
        return self.minlen

class Alt(Tuple):
    def __repr__(self):
        return ' | '.join(map(repr, self))

class Ore(Tuple):
    @classmethod
    def expand(cls, e):
        choice = []
        _expand(e, choice)
        return choice[0] if len(choice)==1 else Ore(*choice)
    
    def __repr__(self):
        return ' / '.join(map(repr, self))
    
    def listDic(self):
        dic = [e.text for e in self if isinstance(e, Char)]
        dic2 = []
        for s in dic:
            if s == '':break
            dic2.append(s)
        return dic2
    
    def trieDic(self, dic = None):
        if dic is None:
            dic = self.listDic()
        if '' in dic or len(dic) < 10:
            return dic
        d = {}
        for s in dic:
            s0, s = s[0], s[1:]
            if s0 in d:
                ss = d[s0]
                if not s in ss:
                    ss.append(s)
            else:
                d[s0] = [s]
        for key in d:
            d[key] = self.trieDic(d[key])
        return d



def _expand(e, choice=[]):
    s = e
    while isinstance(e, Ref):
        e = e.deref()
    if isinstance(e, Ore):
        for x in e:
            _expand(x, choice)
    else:
        choice.append(s)


class Unary(ParsingExpression):
    __slot__ = ['e']

    def __init__(self, e):
        self.e = e

    def __iter__(self):
        yield self.e

    def __len__(self):
        return 1

    def minLen(self): return self.e.minLen()



class And(Unary):
    def __repr__(self):
        return '&'+grouping(self.e, inUnary)

    def minLen(self): return 0


class Not(Unary):
    def __repr__(self):
        return '!'+grouping(self.e, inUnary)

    def minLen(self): return 0

class Many(Unary):
    def __repr__(self):
        return grouping(self.e, inUnary)+'*'

    def minLen(self): return 0

class Many1(Unary):
    def __repr__(self):
        return grouping(self.e, inUnary)+'+'

class Option(Unary):
    def __repr__(self):
        return grouping(self.e, inUnary)+'?'


class Node(Unary):
    __slot__ = ['e', 'tag']

    def __init__(self, e, tag=''):
        self.e = e
        self.tag = tag

    def __repr__(self):
        return '{' + repr(self.e) + ' #' + self.tag + '}'


class Edge(Unary):
    __slot__ = ['e', 'edge']

    def __init__(self, edge, e):
        self.e = e
        self.edge = edge

    def __repr__(self):
        return self.edge + ': ' + grouping(self.e, inUnary)


class Fold(Unary):
    __slot__ = ['e', 'edge', 'tag']

    def __init__(self, edge, e, tag=''):
        self.e = e
        self.edge = edge
        self.tag = tag

    def __repr__(self):
        if self.edge == '':
            return '^ {' + repr(self.e) + ' #' + self.tag + '}'
        return self.edge + ': ^ {' + repr(self.e) + ' #' + self.tag + '}'

class Abs(Unary):
    __slot__ = ['e']

    def __init__(self, e):
        self.e = e

    def __repr__(self):
        return f'@abs({self.e})'

# Action

class Action(Unary):
    __slots__ = ['e', 'func', 'params']
    def __init__(self, e, func, params, pos4=None):
        self.e = e
        self.func = func
        self.params = params

    def __repr__(self):
        return f'@{self.func}{self.params}'


# CONSTANT
EMPTY = Char('')
ANY = Any()
FAIL = Not(EMPTY)

def pEmpty(): return EMPTY
def pAny(): return ANY
def pChar(c): return Char(c) if len(c) > 0 else EMPTY
def pRange(cs, rs): return Range(cs, rs)
def pAnd(e): return And(e)
def pNot(e): return Not(e)
def pMany(e): return Many(e)
def pMany1(e): return Many1(e)
def pOption(e): return Option(e)
def pSeq(*es): return Seq(*es)
def pSeq2(e,e2): return Seq(e,e2)
def pSeq3(e,e2,e3): return Seq(e,e2,e3)
def pOre(*es): return Ore(*es)
def pOre2(e,e2): return Ore(e,e2)
def pOre3(e,e2,e3): return Ore(e,e2,e3)
def pRef(peg, name): return Ref(peg, name)
def pNode(e, tag, shift): return Node(e, tag)
def pEdge(label,e): return Edge(label, e) if label != '' else e
def pFold(label, e, tag, shift): return Fold(label, e, tag)

# repr

def grouping(e, f):
    return '(' + repr(e) + ')' if f(e) else repr(e)

def inUnary(e):
    return isinstance(e, Ore) \
        or isinstance(e, Seq) or isinstance(e, Alt) \
        or (isinstance(e, Edge))or isinstance(e, Fold)

CharTBL = str.maketrans(
    {'\n': '\\n', '\t': '\\t', '\r': '\\r', '\v': '\\v', '\f': '\\f',
     '\\': '\\\\', "'": "\\'"})

RangeTBL = str.maketrans(
    {'\n': '\\n', '\t': '\\t', '\r': '\\r', '\v': '\\v', '\f': '\\f',
    '\\': '\\\\', ']': '\\]', '-': '\\-'})

def rs(ranges):
    ss = tuple(map(lambda x: x[0].translate(
        RangeTBL) + '-' + x[1].translate(RangeTBL), ranges))
    return ''.join(ss)

def ss(e): 
    return grouping(e, lambda e: isinstance(e, Ore) or isinstance(e, Alt))

# # Grammar

GrammarId = 0

class Grammar(dict):
    def __init__(self):
        global GrammarId
        self.gid = str(GrammarId)
        self.N = []
        GrammarId += 1
        super().__setitem__('@@example', [])



    def __repr__(self):
        ss = []
        for rule in self.N:
            ss.append(rule)
            ss.append(' = ')
            ss.append(repr(self[rule]))
            ss.append('\n')
        return ''.join(ss)

    # def add(self, key, item):
    #     if not key in self:
    #         self.N.append(key)
    #     self[key] = item

    def __setitem__(self, key, item):
        if not key in self:
            self.N.append(key)
        super().__setitem__(key, item)

    def newRef(self, name):
        key = '@' + name
        if key not in self:
            super().__setitem__(key, Ref(self, name))
        return self[key]

    def start(self):
        if len(self.N) == 0:
            self['EMPTY'] = EMPTY
        return self.N[0]

def TPEG(peg):
    peg['Start'] = pSeq3(pRef(peg,'__'),pRef(peg,'Source'),pRef(peg,'EOF'));
    peg['__'] = pMany(pOre2(pRange(' \t\r\n',[]),pRef(peg,'COMMENT')));
    peg['_'] = pMany(pOre2(pRange(' \t',[]),pRef(peg,'COMMENT')));
    peg['COMMENT'] = pOre2(pSeq3(pChar('/*'),pMany(pSeq2(pNot(pChar('*/')),pAny())),pChar('*/')),pSeq2(pChar('//'),pMany(pSeq2(pNot(pRef(peg,'EOL')),pAny()))));
    peg['EOL'] = pOre(pChar('\n'),pChar('\r\n'),pRef(peg,'EOF'));
    peg['EOF'] = pNot(pAny());
    peg['S'] = pRange(' \t',[]);
    peg['Source'] = pNode(pMany(pEdge('',pRef(peg,'Statement'))),'Source',0);
    peg['EOS'] = pOre2(pSeq2(pRef(peg,'_'),pMany1(pSeq2(pChar(';'),pRef(peg,'_')))),pMany1(pSeq2(pRef(peg,'_'),pRef(peg,'EOL'))));
    peg['Statement'] = pOre(pRef(peg,'Import'),pRef(peg,'Example'),pRef(peg,'Rule'));
    peg['Import'] = pSeq2(pNode(pSeq(pChar('from'),pRef(peg,'S'),pRef(peg,'_'),pEdge('name',pOre2(pRef(peg,'Identifier'),pRef(peg,'Char'))),pOption(pSeq(pRef(peg,'_'),pChar('import'),pRef(peg,'S'),pRef(peg,'_'),pEdge('names',pRef(peg,'Names'))))),'Import',0),pRef(peg,'EOS'));
    peg['Example'] = pSeq2(pNode(pSeq(pChar('example'),pRef(peg,'S'),pRef(peg,'_'),pEdge('names',pRef(peg,'Names')),pEdge('doc',pRef(peg,'Doc'))),'Example',0),pRef(peg,'EOS'));
    peg['Names'] = pNode(pSeq3(pEdge('',pRef(peg,'Identifier')),pRef(peg,'_'),pMany(pSeq(pChar(','),pRef(peg,'_'),pEdge('',pRef(peg,'Identifier')),pRef(peg,'_')))),'',0);
    peg['Doc'] = pOre(pRef(peg,'Doc1'),pRef(peg,'Doc2'),pRef(peg,'Doc0'));
    peg['Doc0'] = pNode(pMany(pSeq2(pNot(pRef(peg,'EOL')),pAny())),'Doc',0);
    peg['Doc1'] = pSeq(pRef(peg,'DELIM1'),pMany(pRef(peg,'S')),pRef(peg,'EOL'),pNode(pMany(pSeq2(pNot(pSeq2(pRef(peg,'DELIM1'),pRef(peg,'EOL'))),pAny())),'Doc',0),pRef(peg,'DELIM1'));
    peg['DELIM1'] = pChar("'''");
    peg['Doc2'] = pSeq(pRef(peg,'DELIM2'),pMany(pRef(peg,'S')),pRef(peg,'EOL'),pNode(pMany(pSeq2(pNot(pSeq2(pRef(peg,'DELIM2'),pRef(peg,'EOL'))),pAny())),'Doc',0),pRef(peg,'DELIM2'));
    peg['DELIM2'] = pChar('```');
    peg['Rule'] = pSeq2(pNode(pSeq(pEdge('name',pOre2(pRef(peg,'Identifier'),pRef(peg,'QName'))),pRef(peg,'__'),pOre2(pChar('='),pChar('<-')),pRef(peg,'__'),pOption(pSeq2(pRange('/|',[]),pRef(peg,'__'))),pEdge('e',pRef(peg,'Expression'))),'Rule',0),pRef(peg,'EOS'));
    peg['Identifier'] = pNode(pRef(peg,'NAME'),'Name',0);
    peg['NAME'] = pSeq2(pRange('_',['AZ','az']),pMany(pRange('_.',['AZ','az','09'])));
    peg['Expression'] = pSeq2(pRef(peg,'Choice'),pOption(pFold('',pMany1(pSeq(pRef(peg,'__'),pChar('|'),pNot(pChar('|')),pRef(peg,'_'),pEdge('',pRef(peg,'Choice')))),'Alt',0)));
    peg['Choice'] = pSeq2(pRef(peg,'Sequence'),pOption(pFold('',pMany1(pSeq(pRef(peg,'__'),pOre2(pChar('/'),pChar('||')),pRef(peg,'_'),pEdge('',pRef(peg,'Sequence')))),'Ore',0)));
    peg['Sequence'] = pSeq2(pRef(peg,'Predicate'),pOption(pFold('',pMany1(pSeq2(pRef(peg,'SS'),pEdge('',pRef(peg,'Predicate')))),'Seq',0)));
    peg['SS'] = pOre2(pSeq3(pRef(peg,'S'),pRef(peg,'_'),pNot(pRef(peg,'EOL'))),pSeq3(pMany1(pSeq2(pRef(peg,'_'),pRef(peg,'EOL'))),pRef(peg,'S'),pRef(peg,'_')));
    peg['Predicate'] = pOre(pRef(peg,'Not'),pRef(peg,'And'),pRef(peg,'Suffix'));
    peg['Not'] = pSeq2(pChar('!'),pNode(pEdge('e',pRef(peg,'Predicate')),'Not',0));
    peg['And'] = pSeq2(pChar('&'),pNode(pEdge('e',pRef(peg,'Predicate')),'And',0));
    peg['Suffix'] = pSeq2(pRef(peg,'Term'),pOption(pOre(pFold('e',pChar('*'),'Many',0),pFold('e',pChar('+'),'Many1',0),pFold('e',pChar('?'),'Option',0))));
    peg['Term'] = pOre(pRef(peg,'Group'),pRef(peg,'Char'),pRef(peg,'Class'),pRef(peg,'Any'),pRef(peg,'Node'),pRef(peg,'Fold'),pRef(peg,'EdgeFold'),pRef(peg,'Edge'),pRef(peg,'Func'),pRef(peg,'Ref'));
    peg['Empty'] = pNode(pEmpty(),'Empty',0);
    peg['Group'] = pSeq(pChar('('),pRef(peg,'__'),pOre2(pRef(peg,'Expression'),pRef(peg,'Empty')),pRef(peg,'__'),pChar(')'));
    peg['Any'] = pNode(pChar('.'),'Any',0);
    peg['Char'] = pSeq3(pChar("'"),pNode(pMany(pOre2(pSeq2(pChar('\\'),pAny()),pSeq2(pNot(pChar("'")),pAny()))),'Char',0),pChar("'"));
    peg['Class'] = pSeq3(pChar('['),pNode(pMany(pOre2(pSeq2(pChar('\\'),pAny()),pSeq2(pNot(pChar(']')),pAny()))),'Class',0),pChar(']'));
    peg['Node'] = pNode(pSeq(pChar('{'),pRef(peg,'__'),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pEdge('e',pOre2(pSeq2(pRef(peg,'Expression'),pRef(peg,'__')),pRef(peg,'Empty'))),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pRef(peg,'__'),pChar('}')),'Node',0);
    peg['Tag'] = pSeq2(pChar('#'),pNode(pMany1(pSeq2(pNot(pRange(' \t\r\n}',[])),pAny())),'Tag',0));
    peg['Fold'] = pNode(pSeq(pChar('^'),pRef(peg,'_'),pChar('{'),pRef(peg,'__'),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pEdge('e',pOre2(pSeq2(pRef(peg,'Expression'),pRef(peg,'__')),pRef(peg,'Empty'))),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pRef(peg,'__'),pChar('}')),'Fold',0);
    peg['Edge'] = pNode(pSeq(pEdge('edge',pRef(peg,'Identifier')),pChar(':'),pRef(peg,'_'),pNot(pChar('^')),pEdge('e',pRef(peg,'Term'))),'Edge',0);
    peg['EdgeFold'] = pNode(pSeq(pEdge('edge',pRef(peg,'Identifier')),pChar(':'),pRef(peg,'_'),pChar('^'),pRef(peg,'_'),pChar('{'),pRef(peg,'__'),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pEdge('e',pOre2(pSeq2(pRef(peg,'Expression'),pRef(peg,'__')),pRef(peg,'Empty'))),pOption(pSeq2(pEdge('tag',pRef(peg,'Tag')),pRef(peg,'__'))),pRef(peg,'__'),pChar('}')),'Fold',0);
    peg['Func'] = pNode(pSeq(pChar('@'),pEdge('',pRef(peg,'Identifier')),pChar('('),pRef(peg,'__'),pOre2(pEdge('',pRef(peg,'Expression')),pEdge('',pRef(peg,'Empty'))),pMany(pSeq(pRef(peg,'_'),pChar(','),pRef(peg,'__'),pEdge('',pRef(peg,'Expression')))),pRef(peg,'__'),pChar(')')),'Func',0);
    peg['Ref'] = pOre2(pRef(peg,'Identifier'),pRef(peg,'QName'));
    peg['QName'] = pNode(pSeq3(pChar('"'),pMany(pOre2(pSeq2(pChar('\\'),pAny()),pSeq2(pNot(pChar('"')),pAny()))),pChar('"')),'Name',0);
    return peg

TPEGGrammar = TPEG(Grammar())
#print(TPEGGrammar)

######################################################################
# ast.env

def bytestr(b):
    return b.decode('utf-8') if isinstance(b, bytes) else b

#####################################

class PTree(object):
    __slots__ = ['prev', 'tag', 'spos', 'epos', 'child']

    def __init__(self, prev, tag, spos, epos, child):
        self.prev = prev
        self.tag = tag
        self.spos = spos
        self.epos = epos
        self.child = child

    def isEdge(self):
        return self.epos < 0

    def dump(self, inputs):
        sb = []
        if self.prev is not None:
            sb.append(self.prev.dump(inputs))
            sb.append(',')
        sb.append(f'{{#{self.tag} ')
        if self.child is None:
            sb.append(repr(inputs[self.spos:self.epos]))
        else:
            sb.append(self.child.dump(inputs))
        sb.append('}')
        return ''.join(sb)

def splitPTree(pt):
    if pt is None: return None, None
    if pt.prev is None: return None, pt
    return pt.prev, PTree(None, pt.tag, pt.spos, pt.epos, pt.child)

def makePTree(pt: PTree, inputs: str):
    ns = []
    while pt != None:
        if pt.child == None:
            child = repr(inputs[pt.spos:pt.epos])
        else:
            child = makePTree(pt.child)
        child = (pt.tag, child)
        ns.append(child)
        pt = pt.prev
    if len(ns) == 1:
        return ns[0]
    return list(reversed(ns))


def PTree2ParseTree(pt: PTree, urn, inputs):
    if pt.prev != None:
        return PTree2ParseTreeImpl('', urn, inputs, pt.spos, pt.epos, pt)
    else:
        return PTree2ParseTreeImpl(pt.tag, urn, inputs, pt.spos, pt.epos, pt.child)


def PTree2ParseTreeImpl(tag, urn, inputs, spos, epos, subnode):
    t = ParseTree(tag, inputs, spos, epos, urn)
    while subnode != None:
        if subnode.isEdge():
            if subnode.child == None:
                tt = PTree2ParseTreeImpl(
                    '', urn, inputs, subnode.spos, abs(subnode.epos), None)
            else:
                tt = PTree2ParseTree(subnode.child, urn, inputs)
            if subnode.tag == '':
                t.append(tt)
            else:
                setattr(t, subnode.tag, tt)
        else:
            t.append(PTree2ParseTreeImpl(subnode.tag, urn, inputs,
                                         subnode.spos, abs(subnode.epos), subnode.child))
        subnode = subnode.prev
    for i in range(len(t)//2):
      t[i], t[-(1+i)] = t[-(1+i)],t[i]
    return t



# ParserContext

State = namedtuple('State', 'sid val prev')


class Memo(object):
    __slots__ = ['key', 'pos', 'ast', 'result']

    def __init__(self):
        self.key = -1
        self.pos = 0
        self.ast = None
        self.result = False


class ParserContext:
    __slots__ = ['inputs', 'pos', 'epos',
                 'headpos', 'ast', 'state', 'memo']

    def __init__(self, inputs, spos, epos):
        self.inputs = inputs
        self.pos = spos
        self.epos = epos
        self.headpos = spos
        self.ast = None
        self.state = None
        self.memo = [Memo() for x in range(1789)]

    def getstate(self, state, sid):
        while state is not None:
            if state.sid == sid:
                return state
            state = state.prev
        return None

# Generator


def match_empty(px): return True


def match_any(px):
    if px.pos < px.epos:
        px.pos += 1
        return True
    return False


class Generator(object):
    def __init__(self):
        self.peg = None
        self.generated = {}
        self.generating_nonterminal = ''
        self.cache = {'': match_empty}
        self.sids = {}

    def getsid(self, name):
        if not name in self.sids:
            self.sids[name] = len(self.sids)
        return self.sids[name]

    def makelist(self, pe, v: dict, ps: list):
        if isinstance(pe, Ref):
            u = pe.uname()
            if u not in self.generated and u not in v:
                v[u] = pe
                self.makelist(pe.deref(), v, ps)
                ps.append(pe)
            return ps
        if isinstance(pe, Unary) or isinstance(pe, Tuple):
            for e in pe:
                self.makelist(e, v, ps)
        return ps

    def generate(self, peg, **option):
        self.peg = peg
        name = option.get('start', peg.start())
        start = peg.newRef(name)
        # if 'memos' in option and not isinstance(option['memos'], list):
        memos = option.get('memos', peg.N)
        ps = self.makelist(start, {}, [])

        for ref in ps:
            assert isinstance(ref, Ref)
            uname = ref.uname()
            self.generating_nonterminal = uname
            A = self.emit(ref.deref(), 0)
            self.generating_nonterminal = ''
            idx = memos.index(ref.name)
            # if idx != -1 and ref.peg == peg:
            #     A = self.memoize(idx, len(memos), A)
            self.generated[uname] = A

        pf = self.generated[start.uname()]

        def parse(inputs, urn='(unknown source)', pos=0, epos=None, conv=PTree2ParseTree):
            if epos is None:
                epos = len(inputs)
            px = ParserContext(inputs, pos, epos)
            if not pf(px):
                result = PTree(None, "err", px.headpos, px.headpos, None)
            else:
                result = px.ast if px.ast is not None else PTree(None,
                                                                 "", pos, px.pos, None)
            return conv(result, urn, inputs)
        return parse

    def emit(self, pe: ParsingExpression, step: int):
        if isinstance(pe, Action):
            cname = pe.func
        else:
            cname = pe.__class__.__name__
        if hasattr(self, cname):
            f = getattr(self, cname)
            return f(pe, step)
        print('@TODO(Generator)', cname, pe)
        return match_empty

    def memoize(self, mp, msize, A):
        def match_memo(px):
            key = (msize * px.pos) + mp
            m = px.memo[key % 1789]
            if m.key == key:
                px.pos = m.pos
                if m.ast != False:
                    px.ast = m.ast
                return m.result
            prev = px.ast
            m.result = A(px)
            m.pos = px.pos
            m.ast = px.ast if prev != px.ast else False
            m.key = key
            return m.result
        return match_memo

    def Any(self, pe, step):
        return match_any

    def Char(self, pe, step):
        if pe.text in self.cache:
            return self.cache[pe.text]
        chars = pe.text
        clen = len(pe.text)
        #

        def match_char(px):
            if px.inputs.startswith(chars, px.pos):
                px.pos += clen
                return True
            return False
        self.cache[pe.text] = match_char
        return match_char

    def Range(self, pe, step):
        bitset = unique_range(pe.chars, pe.ranges)  # >> offset

        def match_bitset(px):
            if px.pos < px.epos:
                shift = ord(px.inputs[px.pos])  # - offset
                if shift >= 0 and (bitset & (1 << shift)) != 0:
                    px.pos += 1
                    return True
            return False

        return match_bitset

    def And(self, pe, step):
        pf = self.emit(pe.e, step)

        def match_and(px):
            pos = px.pos
            if pf(px):
                # backtracking
                px.headpos = max(px.pos, px.headpos)
                px.pos = pos
                return True
            return False

        return match_and

    def Not(self, pe, step):
        pf = self.emit(pe.e, step)

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

    def Many(self, pe, step):
        pf = self.emit(pe.e, step)

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

    def Many1(self, pe, step):
        pf = self.emit(pe.e, step)

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

    def Option(self, pe, step):
        pf = self.emit(pe.e, step)

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

    def Seq(self, pe, step):
        #if len(pe) == 2:
        #    return self.Seq2(pe)
        #if len(pe) == 3:
        #    return self.Seq3(pe)
        #
        pfs = []
        for e in pe:
            pfs.append(self.emit(e, step))
            step += e.minLen()
        pfs = tuple(pfs)

        def match_seq(px):
            for pf in pfs:
                if not pf(px):
                    return False
            return True
        return match_seq

    # Ore
    def OreDic(self, dic: list):
        d = trie(dic)

        def match_trie(px, d):
            if px.pos >= px.epos:
                return False
            if isinstance(d, dict):
                c = px.inputs[px.pos]
                if c in d:
                    px.pos += 1
                    return match_trie(px, d[c])
                return False
            pos = px.pos
            inputs = px.inputs
            for s in d:
                if inputs.startswith(s, pos):
                    px.pos += len(s)
                    return True
            return False

    def Ore(self, pe, step):
        # pe2 = Ore.expand(pe)
        # if not isinstance(pe2, Ore):
        #     return self.emit(pe2)
        # pe = pe2
        # dic = pe.listDic()
        # if len(dic) == len(pe):
        #     d = pe.trieDic(dic)
        #     return lambda px: match_trie(px, d)

        pfs = tuple(map(lambda e: self.emit(e, step), pe))

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

    def Ref(self, pe, step):
        uname = pe.uname()
        generated = self.generated
        if uname not in generated:
            generated[uname] = lambda px: generated[uname](px)
        return generated[uname]

    # Tree Construction

    def Node(self, pe, step):
        pf = self.emit(pe.e, step)
        node = pe.tag

        def make_tree(px):
            pos = px.pos
            prev = px.ast
            px.ast = None
            if pf(px):
                px.ast = PTree(prev, node, pos, px.pos, px.ast)
                return True
            #px.ast = prev
            return False

        return make_tree

    def Edge(self, pe, step):
        pf = self.emit(pe.e, step)
        edge = pe.edge
        #if edge == '': return pf

        def match_edge(px):
            pos = px.pos
            prev = px.ast
            px.ast = None
            if pf(px):
                px.ast = PTree(prev, edge, pos, -px.pos, px.ast)
                return True
            #px.ast = prev
            return False
        return match_edge

    def Fold(self, pe, step):
        pf = self.emit(pe.e, step)
        node = pe.tag
        edge = pe.edge

        def match_fold(px):
            pos = px.pos
            #pprev = px.ast
            prev, pt = splitPTree(px.ast)
            px.ast = pt if edge == '' else PTree(None, edge, 0, -pos, pt)
            if pf(px):
                px.ast = PTree(prev, node, pos, px.pos, px.ast)
                return True
            #px.ast = pprev
            return False
        return match_fold

    def Abs(self, pe, step):
        pf = self.emit(pe.e, step)

        def match_abs(px):
            ast = px.ast
            if pf(px):
                px.ast = ast
                return True
            return False
        return match_abs

    # StateTable

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

    def Lazy(self, pe, step):  # @lazy(A)
        name = pe.e.name
        peg = self.peg
        return peg.newRef(name).gen(**option) if name in peg else pe.e.gen(**option)

    def Skip(self, pe, step):  # @skip()
        def skip(px):
            px.pos = min(px.headpos, px.epos)
            return True
        return skip

    def Symbol(self, pe, step):  # @symbol(A)
        params = pe.params
        sid = self.getsid(str(params[0]))
        pf = self.emit(pe.e, step)

        def match_symbol(px):
            pos = px.pos
            if pf(px):
                px.state = State(sid, px.inputs[pos:px.pos], px.state)
                return True
            return False
        return match_symbol

    def Scope(self, pe, step):
        pf = self.emit(pe.e, step)

        def scope(px):
            state = px.state
            res = pf(px)
            px.state = state
            return res
        return scope

    def Exists(self, pe, step):  # @Match(A)
        params = pe.params
        sid = self.getsid(str(params[0]))
        return lambda px: px.getstate(px.state, sid) != None

    def Match(self, pe, step):  # @Match(A)
        params = pe.params
        sid = self.getsid(str(params[0]))
        #pf = self.emit(pe.e)

        def match(px):
            state = px.getstate(px.state, sid)
            if state is not None and px.inputs.startswith(state.val, px.pos):
                px.pos += len(state.val)
                return True
            return False
        return match

    def Def(self, pe, step):
        params = pe.params
        name = str(params[0])
        pf = self.emit(pe.e, step)

        def define_dict(px):
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
        return define_dict

    def In(self, pe, step):  # @in(NAME)
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

    '''
            if fname == 'on':  # @on(!A, e)
            name = str(params[0])
            pf = pe.e.gen(**option)
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
    '''

generator = Generator()

def generate(peg: Grammar, **options):
  return generator.generate(peg, **options)

# ParseTree

UNKNOWN_URN = '(unknown source)'


def rowcol(urn, inputs, spos):
    inputs = inputs[:spos + (1 if len(inputs) > spos else 0)]
    rows = inputs.split(b'\n' if isinstance(inputs, bytes) else '\n')
    return urn, spos, len(rows), len(rows[-1])-1


def nop(s): return s


class ParseTree(list):
    def __init__(self, tag, inputs, spos=0, epos=None, urn=UNKNOWN_URN):
        self.tag_ = tag
        self.inputs_ = inputs
        self.spos_ = spos
        self.epos_ = epos if epos is not None else len(inputs)
        self.urn_ = urn

    def gettag(self):
        return self.tag_

    def start(self):
        return rowcol(self.urn_, self.inputs_, self.spos_)

    def end(self):
        return rowcol(self.urn_, self.inputs_, self.epos_)

    def decode(self):
        inputs, spos, epos = self.inputs_, self.spos_, self.epos_
        LF = b'\n' if isinstance(inputs, bytes) else '\n'
        rows = inputs[:spos + (1 if len(inputs) > spos else 0)]
        rows = rows.split(LF)
        linenum, column = len(rows), len(rows[-1])-1
        begin = inputs.rfind(LF, 0, spos) + 1
        #print('@', spos, begin, inputs)
        end = inputs.find(LF, spos)
        #print('@', spos, begin, inputs)
        if end == -1:
            end = len(inputs)
        #print('@[', begin, spos, end, ']', epos)
        line = inputs[begin:end]  # .replace('\t', '   ')
        mark = []
        endcolumn = column + (epos - spos)
        for i, c in enumerate(line):
            if column <= i and i <= endcolumn:
                mark.append('^' if ord(c) < 256 else '^^')
            else:
                mark.append(' ' if ord(c) < 256 else '  ')
        mark = ''.join(mark)
        return (self.urn_, spos, linenum, column, bytestr(line), mark)

    def showing(self, msg='Syntax Error'):
        urn, pos, linenum, cols, line, mark = self.decode()
        return '{} ({}:{}:{}+{})\n{}\n{}'.format(msg, urn, linenum, cols, pos, line, mark)

    def __eq__(self, tag):
        return self.tag_ == tag

    def isSyntaxError(self):
        return self.tag_ == 'err'

    def __str__(self):
        s = self.inputs_[self.spos_:self.epos_]
        return s.decode('utf-8') if isinstance(s, bytes) else s

    def __repr__(self):
        if self.isSyntaxError():
            return self.showing('Syntax Error')
        sb = []
        self.strOut(sb)
        return "".join(sb)

    def dump(self, indent='\n  ', tab='  ', tag=nop, edge=nop, token=nop):
        if self.isSyntaxError():
            return self.showing('Syntax Error')
        sb = []
        self.strOut(sb)
        return "".join(sb)

    def strOut(self, sb, indent='\n  ', tab='  ', tag=nop, edge=nop, token=nop):
        sb.append("[" + tag(f'#{self.tag_}'))
        hasContent = False
        next_indent = indent + tab
        for child in self:
            hasContent = True
            sb.append(indent)
            if hasattr(child, 'strOut'):
                child.strOut(sb, next_indent, tab, tag, edge, token)
            else:
                sb.append(repr(child))
        for key in self.__dict__:
            v = self.__dict__[key]
            if isinstance(v, ParseTree):
                hasContent = True
                sb.append(indent)
                sb.append(edge(key) + ': ')
                v.strOut(sb, next_indent, tab, tag, edge, token)
        if not hasContent:
            sb.append(' ' + token(repr(str(self))))
        sb.append("]")

class TPEGLoader(object):
    def __init__(self, peg):
        self.names = {}
        self.peg = peg

    def load(self, t: ParseTree):
        for stmt in t:
            if stmt == 'Rule':
                name = str(stmt.name)
                if name in self.names:
                    pos4 = stmt['name'].getpos4()
                    logger('error', stmt.name, f'redefined name {name}')
                    continue
                self.names[name] = stmt.e
            elif stmt == 'Example':
                doc = stmt.doc
                for n in stmt.names:
                    self.example(str(n), doc)
            # elif stmt == 'Import':
            #     urn = str(stmt.name)
            #     apeg = grammar(urn, **options)
            #     for n in stmt.names:
            #         lname = str(n)  # ns.Expression
            #         name = lname
            #         if lname.find('.') != -1:
            #             name = lname.split('.')[-1]
            #         pos4 = n.getpos4()
            #         if not name in apeg:
            #             logger('perror', pos4, f'undefined name {name}')
            #             continue
            #         g.add(lname, Action(apeg.newRef(name),
            #                             'import', (name, urn), pos4))
        for name in self.names:
            t = self.names[name]
            self.peg[name] = self.conv(t, 0)

    def example(self, name, doc):
        self.peg['@@example'].append((name, doc))

    def conv(self, t: ParseTree, step):
        tag = t.gettag()
        if hasattr(self, tag):
            f = getattr(self, tag)
            return f(t, step)
        return t
    
    @classmethod
    def unquote(cls, s):
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
            if (s.startswith('\\x') or s.startswith('\\X')) and len(s) >= 4:
                c = int(s[2:4], 16)
                return chr(c), s[4:]
            if (s.startswith('\\u') or s.startswith('\\U')) and len(s) >= 6:
                c = chr(int(s[2:6], 16))
                if len(c) != 1: c = ''  # remove unsupported unicode
                return c, s[6:]
            else:
                return s[1], s[2:]
        else:
            return s[0], s[1:]

    @classmethod
    def choice(t: ParseTree, file):
        urn, _, _, _ = t.pos()
        file = str(file)[1:-1]
        file = Path(urn).parent / file
        with file.open(encoding='utf-8_sig') as f:
            ss = [x.strip('\r\n') for x in f.readlines()]
            ss = [x for x in ss if len(x) > 0 and not x.startswith('#')]
            ss = sorted(ss, key=lambda x: len(x))[::-1]
            choice = [Char(x) for x in ss]
            e = Ore(*choice)
            DEBUG(file, e)
            return e
        return EMPTY

    def Empty(self, t, step):
        return EMPTY

    def Any(self, t, step):
        return ANY

    def Char(self, t, step):
        s = str(t)
        sb = []
        while len(s) > 0:
            c, s = TPEGLoader.unquote(s)
            sb.append(c)
        return pChar(''.join(sb))

    def Class(self, t, step):
        s = str(t)
        chars = []
        ranges = []
        while len(s) > 0:
            c, s = TPEGLoader.unquote(s)
            if s.startswith('-') and len(s) > 1:
                c2, s = TPEGLoader.unquote(s[1:])
                ranges.append((c, c2))
            else:
                chars.append(c)
        if len(chars) == 1 and len(ranges) == 0:
            return pChar(chars[0])
        return Range(''.join(chars), ranges)

    def Ref(self, t, step):
        name = str(t)
        if name in self.peg:
            return Action(self.peg.newRef(name), 'NT', (name,), t.getpos4())
        if name[0].isupper() or name[0].islower() or name.startswith('_'):
            logger('warning', t, f'undefined nonterminal {name}')
            self.peg.add(name, EMPTY)
            return self.peg.newRef(name)
        return pChar(name[1:-1]) if name.startswith('"') else char1(name)

    def Name(self, t, step):
        name = str(t)
        if name in self.names:
            return self.peg.newRef(name)
        if name[0].isupper() or name[0].islower() or name.startswith('_'):
            default_logger('warning', t, f'undefined nonterminal {name}')
            self.peg.add(name, EMPTY)
            return self.peg.newRef(name)
        return pChar(name[1:-1]) if name.startswith('"') else char1(name)



    def Many(self, t, step):
        return Many(self.conv(t.e, step))

    def Many1(self, t, step):
        return Many1(self.conv(t.e, step))

    def Option(self, t, step):
        return Option(self.conv(t.e, step))

    def And(self, t, step):
        return And(self.conv(t.e, step))

    def Not(self, t, step):
        return Not(self.conv(t.e, step))

    def Seq(self, t, step):
        es = []
        for p in t:
            e = self.conv(p, step)
            #step += e.minLen()
            es.append(e)
        return pSeq(*es)

    def Ore(self, t, step):
        return pOre(*tuple(map(lambda p: self.conv(p, step), t)))

    def Alt(self, t, step):
        return pAlt(*tuple(map(lambda p: self.conv(p, step), t)))

    def Node(self, t, step):
        tag = str(t.tag) if hasattr(t, 'tag') else ''
        e = self.conv(t.e, step)
        return pNode(e, tag, 0)

    def Edge(self, t, step):
        edge = str(t.edge) if hasattr(t, 'edge') else ''
        e = self.conv(t.e, step)
        return pEdge(edge, e)

    def Fold(self, t, step):
        edge = str(t.edge) if hasattr(t, 'edge') else ''
        tag = str(t.tag) if hasattr(t, 'tag') else ''
        e = self.conv(t.e, step)
        return pFold(edge, e, tag, 0)

    # def Append(self, t, logger):
    #     name = ''
    #     tsub = t['inner']
    #     if tsub == 'Func':
    #         a = tsub.asArray()
    #         name = str(a[0])
    #         inner = self.conv(a[1], logger)
    #     else:
    #         inner = self.conv(tsub, logger)
    #     return Edge(inner, name)

    FIRST = {'lazy', 'scope', 'symbol',
             'match', 'equals', 'contains', 'cat'}

    def Func(self, t, step):
        funcname = str(t.name)
        ps = [self.conv(p, step) for p in t.params]
        if funcname == 'choice' and len(ps) > 0:
            return TPEGLoader.choice(t, ps[0])
        if funcname in PEGConv.FIRST:
            return Action(ps[0], funcname, tuple(ps), t)
        return Action(EMPTY, funcname, tuple(ps), t)

def grammar_factory():

    def default_logger(type, pos, msg):
        print(pos.showing(msg))

    def load_grammar(g, file, **options):
        logger = options.get('logger', default_logger)
        pegparser = generate(options.get('peg', TPEGGrammar))
        if isinstance(file, Path):
            f = file.open(encoding=options.get('encoding', 'utf-8_sig'))
            data = f.read()
            f.close()
            t = pegparser(data, file)
            basepath = str(file)
        else:
            if 'basepath' in options:
                basepath = options['basepath']
            else:
                basepath = inspect.currentframe().f_back.f_code.co_filename
            t = pegparser(file, basepath)
            basepath = (str(Path(basepath).resolve().parent))
        options['basepath'] = basepath
        if t == 'err':
            logger('error', t, 'Syntax Error')
            return
        pconv = TPEGLoader(g)
        pconv.load(t)

    def findpath(paths, file):
        if file.find('=') > 0:
            return file
        for p in paths:
            path = Path(p) / file
            if path.exists():
                return path.resolve()
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file)

    GrammarDB = {}

    def grammar(urn, **options):
        paths = []
        basepath = options.get('basepath', '')
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
        load_grammar(peg, path, **options)
        GrammarDB[key] = peg
        return peg

    return grammar

grammar = grammar_factory()

def makeNonterminalList(peg, pe, ns: list, es):
    if isinstance(pe, Ref):
        uname = pe.uname() if pe.peg != peg else pe.name
        if uname not in ns:
            ns.append(uname)
            es[uname] = pe.deref()
            makeNonterminalList(peg, es[uname], ns, es)
    if isinstance(pe, Unary):
        makeNonterminalList(peg, pe.e, ns, es)
    elif isinstance(pe, Tuple):
      for e in pe:
        makeNonterminalList(peg, e, ns, es)

# NezCC

class Combinator(object):
    ESCTBL = str.maketrans(
        {'\n': '\\n', '\t': '\\t', '\r': '\\r', '\v': '\\v', '\f': '\\f',
         '\\': '\\\\', "'": "\\'", '"': "\\\""})

    def __init__(self, options = {}):
        self.SIDs = {}
        self.apply = options.get('apply', '{}({})')
        self.delim = options.get('delim', ',')
        self.prefix = options.get('prefix', 'p')
        self.funcs = set(options.get('supported', []))

    def has(self, funcname):
        return funcname in self.funcs

    def emitAll(self, peg, start=None):
        ns = [peg.start() if start is None else start]
        es = {ns[0]: peg[ns[0]] }
        makeNonterminalList(peg, peg[ns[0]], ns, es)
        ns.reverse()
        for n in ns:
            ref = self.getref(n)
            print(f'peg[{ref}] = {self.emit(es[n])}')

    def emitApply(self, name, *args):
        name = f'{self.prefix}{name}'
        if len(args) == 0:
            return self.apply.format(name, '')
        elif len(args) == 1:
            return self.apply.format(name, args[0])
        else:
            return self.apply.format(name, self.delim.join(args))

    def quote(self, s):
        if isinstance(s, tuple) or isinstance(s, list):
            sb = []
            for r in s:
              sb.append(r[0]+r[1])
            s = ''.join(sb)
        '"' + s.translate(Combinator.ESCTBL) + '"'
        return '"' + s.translate(Combinator.ESCTBL) + '"'

    def getref(self, name):
        return self.quote(name)

    def emit(self, pe):
        tag = pe.__class__.__name__
        if tag == 'Action':
            tag = pe.func.capitalize()
        if hasattr(self, tag):
            f = getattr(self, tag)
            return f(pe)
        else:
            return self.Undefined(pe)

    def Undefined(self, pe):
        return f'TODO({pe})'

    def Char(self, pe):
        if len(pe.text) == 0:
            return self.emitApply('Empty')
        return self.emitApply('Char', self.quote(pe.text))

    def Range(self, pe):
        return self.emitApply('Range', self.quote(pe.chars), self.quote(pe.ranges))

    def Any(self, pe):
        return self.emitApply('Any')

    def And(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('And', e)

    def Not(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Not', e)

    def Many(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Many', e)

    def Many1(self, pe):
        e = self.emit(pe.e)
        if self.has('Option'):
          return self.emitApply('Many1', e)
        return self.emitApply('Seq2', e, self.emitApply('Many', e))

    def Option(self, pe):
        e = self.emit(pe.e)
        if self.has('Option'):
          return self.emitApply('Option', e)
        return self.emitApply('Ore2', e, self.emitApply('Empty'))

    def emitBinary(self, name, fs):
        if len(fs) == 1: return fs[0]
        if len(fs) == 2:
            return self.emitApply(f'{name}2', fs[0], fs[1])
        if self.has(f'{name}4') and len(fs) >= 4 :
            return self.emitApply(f'{name}4', fs[0], fs[1], fs[2], self.emitBinary(name, fs[3:]))
        if self.has(f'{name}3') and len(fs) >= 3:
            return self.emitApply(f'{name}3', fs[0], fs[1], self.emitBinary(name,fs[2:]))
        return self.emitApply(f'{name}2', fs[0], self.emitBinary(name, fs[1:]))

    def Seq(self, pe):
        fs = [self.emit(e) for e in pe]
        if len(fs) == 2:
            return self.emitApply('Seq2', *fs)
        if len(fs) == 3 and self.has('Seq3'):
            return self.emitApply('Seq3', *fs)
        if len(fs) == 4 and self.has('Seq4'):
            return self.emitApply('Seq4', *fs)
        if self.has('Seq'):
            return self.emitApply('Seq', *fs)
        return self.emitBinary('Seq', fs)

    def Ore(self, pe):
        fs = [self.emit(e) for e in pe]
        if len(fs) == 2:
            return self.emitApply('Ore2', *fs)
        if len(fs) == 3 and self.has('Ore3'):
            return self.emitApply('Ore3', *fs)
        if len(fs) == 4 and self.has('Ore4'):
            return self.emitApply('Ore4', *fs)
        if self.has('Ore'):
            return self.emitApply('Ore', *fs)
        return self.emitBinary('Ore', fs)

    def Alt(self, pe):
        return self.Ore(pe)

    def Ref(self, pe):
        ref = self.getref(pe.name)
        return self.emitApply('Ref', 'peg', ref)

    def Node(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Node', e, self.quote(pe.tag), '0')

    def Edge(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Edge', self.quote(pe.edge), e)

    def Fold(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Fold', self.quote(pe.edge), e, self.quote(pe.tag), '0')

    def Abs(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Abs', e)

    '''
    def Lazy(self, pe):
        params = pe.params
        name = pe.e.name
        peg = option.get('peg')
        fname = pe.func
        params = pe.params
        return self.Undefined(pe)
    '''

    def Skip(self, pe):
        return self.emitApply('pSkipErr')

    def getsid(self, name):
        if not name in self.SIDs:
            self.SIDs[name] = len(self.SIDs)
        return self.SIDs[name]

    def Symbol(self, pe):
        sid = self.getsid(str(pe.params[0]))
        e = self.emit(pe.e)
        return self.emitApply('Symbol', sid, e)

    def Exists(self, pe):
        sid = self.getsid(str(pe.params[0]))
        return self.emitApply('Exists', sid)

    def Match(self, pe):
        sid = self.getsid(str(pe.params[0]))
        return self.emitApply('Match', sid)

    def Scope(self, pe):
        e = self.emit(pe.e)
        return self.emitApply('Scope', e)

    def example(self, g, options):
        for testcase in g['@@example']:
            name, pos4 = testcase
            if not name in g:
                continue
            text = pos4.inputs[pos4.spos:pos4.epos]
            indent = options['indent']
            print(indent + self.emitApply('example', repr(name), repr(text)))




if __name__ == '__main__':
    peg = grammar('es.tpeg')
    #peg = grammar('test.tpeg')
    print(peg)
    c = Combinator()
    c.emitAll(peg)