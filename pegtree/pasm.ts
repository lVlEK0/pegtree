// PContext

class PContext {
  x: string;
  pos: number;
  epos: number;
  headpos: number;
  ast: PTree | null;
  state: PState | null;
  memos: PMemo[];
  constructor(inputs: string, pos: number, epos: number) {
    this.x = inputs;
    this.pos = pos;
    this.epos = epos;
    this.headpos = pos
    this.ast = null
    this.state = null
    this.memos = [];
    for (var i = 0; i < 1789; i += 1) {
      this.memos.push(new PMemo());
    }
  }
}

class PTree {
  readonly prev: PTree | null;
  readonly tag: string;
  readonly spos: number;
  readonly epos: number;
  readonly child: PTree | null;
  constructor(prev: PTree | null, tag: string, spos: number, epos: number, child: PTree | null) {
    this.prev = prev
    this.tag = tag
    this.spos = spos
    this.epos = epos
    this.child = child
  }

  isEdge() {
    return (this.epos < 0);
  }

  dump(inputs: string) {
    const sb: string[] = []
    if (this.prev !== null) {
      sb.push(this.prev.dump(inputs))
      sb.push(',')
    }
    sb.push(`{#${this.tag} `)
    if (this.child === null) {
      sb.push("'")
      sb.push(inputs.substring(this.spos, this.epos))
      sb.push("'")
    }
    else {
      sb.push(this.child.dump(inputs))
    }
    sb.push('}')
    return sb.join('')
  }
}


export type PFunc = (px: PContext) => boolean;

const match_empty: PFunc = (px: PContext) => true

const pEmpty = () => {
  return match_empty;
}

const match_fail: PFunc = (px: PContext) => false

const pFail = () => {
  return match_fail;
}

const match_any: PFunc = (px: PContext) => {
  if (px.pos < px.epos) {
    px.pos += 1
    return true
  }
  return false;
}

const pAny = () => {
  return match_any;
}

const match_skip: PFunc = (px: PContext) => {
  px.pos = Math.min(px.headpos, px.epos)
  return true
}

const pSkip = () => {
  return match_skip;
}

/* Char */

const CharCache: { [key: string]: PFunc } = {
  '': match_empty
}

const store = (cache: { [key: string]: PFunc }, key: string, gen: () => PFunc) => {
  if (!(key in cache)) {
    cache[key] = gen();
  }
  return cache[key];
}

const pChar = (text: string) => {
  const clen = text.length;
  return store(CharCache, text, () => (px: PContext) => {
    if (px.x.startsWith(text, px.pos)) {
      px.pos += clen
      return true
    }
    return false
  });
}

// const range_min = (chars: string, ranges: string) => {
//   const s = chars + ranges;
//   var min = 0xffff;
//   for (var i = 0; i < s.length; i++) {
//     const c = s.charCodeAt(i)
//     min = Math.min(min, c);
//   }
//   return min;
// }

/* Range */

const range_max = (chars: string, ranges: string) => {
  const s = chars + ranges;
  var min = 0;
  for (var i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i)
    min = Math.max(min, c);
  }
  return min;
}

const range_bitmap = (chars: string, ranges: string) => {
  const codemax = range_max(chars, ranges) + 1;
  const bitmap = new Uint8Array(((codemax / 8) | 0) + 1);
  bitmap[0] = 2;
  for (var i = 0; i < chars.length; i += 1) {
    const c = chars.charCodeAt(i);
    const n = (c / 8) | 0;
    const mask = 1 << ((c % 8) | 0);
    bitmap[n] |= mask;
  }
  for (var i = 0; i < ranges.length; i += 2) {
    for (var c = ranges.charCodeAt(i); c <= ranges.charCodeAt(i + 1); c += 1) {
      const n = (c / 8) | 0;
      const mask = 1 << ((c % 8) | 0);
      bitmap[n] |= mask;
    }
  }
  return bitmap;
}

const RANGETBL: { [key: string]: string } = {
  '\n': '\\n', '\t': '\\t', '\r': '\\r', '\v': '\\v', '\f': '\\f',
  '\\': '\\\\', ']': '\\]', '-': '\\-'
}

export const keyRange = (chars: string, ranges: string) => {
  const sb = []
  sb.push('[')
  sb.push(translate(chars, RANGETBL))
  const r = ranges
  for (var i = 0; i < r.length; i += 2) {
    sb.push(translate(r[i], RANGETBL))
    sb.push('-')
    sb.push(translate(r[i + 1], RANGETBL))
  }
  sb.push(']')
  return sb.join('')
}

const Bitmaps: { [key: string]: Uint8Array } = {}

const toBitmap = (chars: string, ranges: string) => {
  const key = keyRange(chars, ranges);
  if (!(key in Bitmaps)) {
    Bitmaps[key] = range_bitmap(chars, ranges);
  }
  return Bitmaps[key];
}

const bitmatch = (c: number, bitmap: Uint8Array) => {
  const n = (c / 8) | 0;
  const mask = 1 << ((c % 8) | 0);
  return (n < bitmap.length && (bitmap[n] & mask) === mask);
}

const pRange = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    if (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap)) {
      px.pos += 1;
      return true;
    }
    return false;
  }
}

/* And */

const pAnd = (pf: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    if (pf(px)) {
      px.headpos = Math.max(px.pos, px.headpos)
      px.pos = pos
      return true
    }
    return false
  }
}

const pNot = (pf: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    if (!pf(px)) {
      px.headpos = Math.max(px.pos, px.headpos)
      px.pos = pos
      px.ast = ast
      return true
    }
    return false
  }
}

const pMany = (pf: PFunc) => {
  return (px: PContext) => {
    var pos = px.pos
    var ast = px.ast
    while (pf(px) && pos < px.pos) {
      pos = px.pos
      ast = px.ast
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    return true
  }
}

const pMany1 = (pf: PFunc) => {
  return (px: PContext) => {
    if (!pf(px)) {
      return false;
    }
    var pos = px.pos
    var ast = px.ast
    while (pf(px) && pos < px.pos) {
      pos = px.pos
      ast = px.ast
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    return true
  }
}

const pOption = (pf: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    if (!pf(px)) {
      px.headpos = Math.max(px.pos, px.headpos)
      px.pos = pos
      px.ast = ast
    }
    return true
  }
}


const pSeq2 = (pf: PFunc, pf2: PFunc) => {
  return (px: PContext) => {
    return pf(px) && pf2(px)
  }
}

const pSeq3 = (pf: PFunc, pf2: PFunc, pf3: PFunc) => {
  return (px: PContext) => {
    return pf(px) && pf2(px) && pf3(px);
  }
}

const pSeq4 = (pf: PFunc, pf2: PFunc, pf3: PFunc, pf4: PFunc) => {
  return (px: PContext) => {
    return pf(px) && pf2(px) && pf3(px) && pf4(px);
  }
}

const pSeq = (...pfs: PFunc[]) => {
  return (px: PContext) => {
    for (const pf of pfs) {
      if (!pf(px)) {
        return false;
      }
    }
    return true;
  }
}

/* Ore */

const pOre2 = (pf: PFunc, pf2: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    if (pf(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    return pf2(px);
  }
}

const pOre3 = (pf: PFunc, pf2: PFunc, pf3: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    if (pf(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    if (pf2(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    return pf3(px);
  }
}

const pOre4 = (pf: PFunc, pf2: PFunc, pf3: PFunc, pf4: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    if (pf(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    if (pf2(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    if (pf3(px)) {
      return true;
    }
    px.headpos = Math.max(px.pos, px.headpos)
    px.pos = pos
    px.ast = ast
    return pf4(px);
  }
}

const pOre = (...pfs: PFunc[]) => {
  return (px: PContext) => {
    const pos = px.pos
    const ast = px.ast
    for (const pf of pfs) {
      if (pf(px)) {
        return true;
      }
      px.headpos = Math.max(px.pos, px.headpos)
      px.pos = pos
      px.ast = ast
    }
    return false;
  }
}

/* Dict */

const make_words = (ss: string[]) => {
  const dic: { [key: string]: string[] } = {}
  const sss: string[] = [];
  dic[''] = sss;
  for (const w of ss) {
    sss.push(w);
    if (w.length === 0) {
      return dic;
    }
    const key = w.substring(0, 1);
    if (!(key in dic)) {
      dic[key] = [];
    }
    dic[key].push(w.substring(1));
  }
  return dic;
}

type trie = string[] | { [key: string]: string[] | string };

const make_trie = (ss: string[]): trie => {
  const dic = make_words(ss);
  ss = dic[''];
  if (ss.length < 10) {
    return ss;
  }
  delete dic[''];
  for (const key of Object.keys(dic)) {
    ss = dic[key];
    if (ss.length === 1) {
      (dic as any)[key] = ss[0];
    }
    else {
      (dic as any)[key] = make_trie(ss);
    }
  }
  return dic;
}

export const match_trie = (px: PContext, d: trie): boolean => {
  if (Array.isArray(d)) {
    const inputs = px.x;
    const pos = px.pos;
    for (const w of d) {
      if (inputs.startsWith(w, pos)) {
        px.pos += w.length;
        return true
      }
    }
    return false;
  }
  else if (px.pos < px.epos) {
    const c = px.x[px.pos++];
    const suffix = d[c];
    if (typeof suffix === 'string') {
      if (px.x.startsWith(suffix, px.pos)) {
        px.pos += (suffix.length);
        return true
      }
      return false;
    }
    return suffix !== undefined ? match_trie(px, suffix) : false;
  }
  return false
}

const pDict = (words: string) => {
  const trie = make_trie(words.split(' '));
  if (Array.isArray(trie)) {
    const ss: string[] = trie;
    return (px: PContext) => {
      const pos = px.pos
      for (const s of ss) {
        if (px.x.startsWith(s, pos)) {
          px.pos += s.length;
          return true;
        }
      }
      return false;
    }
  }
  else {
    return (px: PContext) => match_trie(px, trie);
  }
}

/* Ref */

const pRef = (generated: any, uname: string) => {
  if (!(uname in generated)) {
    generated[uname] = (px: PContext) => generated[uname](px);
  }
  return generated[uname];
}

class PMemo {
  key: number;
  pos: number;
  treeState: boolean;
  prev: PTree | null;
  ast: PTree | null;
  result: boolean;
  constructor() {
    this.key = -1
    this.pos = 0
    this.ast = null
    this.prev = null
    this.result = false
    this.treeState = false
  }
}

const pMemo = (pf: PFunc, mp: number, mpsize: number) => {
  var disabled = false
  var hit = 0
  var miss = 0
  return (px: PContext) => {
    if (disabled) return pf(px)
    const key = (mpsize * px.pos) + mp
    const m = px.memos[(key % 1789) | 0]
    if (m.key == key) {
      if (m.treeState) {
        if (m.prev === px.ast) {
          px.pos = m.pos
          px.ast = m.ast
          hit += 1
          return m.result
        }
      }
      else {
        px.pos = m.pos;
        return m.result;
      }
    }
    const prev = px.ast;
    m.result = pf(px);
    m.pos = px.pos
    m.key = key
    if (m.result && prev != px.ast) {
      m.treeState = true
      m.prev = prev
      m.ast = px.ast
    }
    else {
      m.treeState = false
    }
    miss += 1;
    if (miss % 100 === 0 && (hit / miss) < 0.05) {
      disabled = false
    }
    return m.result
  }
}

/* Tree Construction */

const pNode = (pf: PFunc, tag: string, shift: number) => {
  return (px: PContext) => {
    const pos = px.pos
    const prev = px.ast
    px.ast = null;
    if (pf(px)) {
      px.ast = new PTree(prev, tag, pos + shift, px.pos, px.ast);
      return true;
    }
    return false;
  }
}

const pEdge = (edge: string, pf: PFunc) => {
  if (edge === '') {
    return pf;
  }
  return (px: PContext) => {
    const pos = px.pos
    const prev = px.ast
    px.ast = null;
    if (pf(px)) {
      px.ast = new PTree(prev, edge, pos, -px.pos, px.ast);
      return true;
    }
    return false;
  }
}

const pFold = (edge: string, pf: PFunc, tag: string, shift: number) => {
  if (edge !== '') {
    return (px: PContext) => {
      const pos = px.pos
      var pt = px.ast;
      const prev = pt ? pt.prev : null;
      pt = pt ? (prev ? new PTree(null, pt.tag, pt.epos, pt.epos, pt.child) : pt) : null;
      px.ast = new PTree(null, edge, pos, -pos, pt);
      if (pf(px)) {
        px.ast = new PTree(prev, tag, pos, px.pos + shift, px.ast);
        return true;
      }
      return false;
    }
  }
  else {
    return (px: PContext) => {
      const pos = px.pos
      const pt = px.ast;
      const prev = (pt !== null) ? pt.prev : null;
      px.ast = pt ? (prev ? new PTree(null, pt.tag, pt.spos, pt.epos, pt.child) : pt) : null;
      if (pf(px)) {
        px.ast = new PTree(prev, tag, pos, px.pos + shift, px.ast);
        return true;
      }
      return false;
    }
  }
}

const pAbs = (pf: PFunc) => {
  return (px: PContext) => {
    const ast = px.ast
    if (pf(px)) {
      px.ast = ast;
      return true;
    }
    return false;
  }
}

// State 

class PState {
  sid: number;
  val: any;
  prev: PState | null;
  constructor(sid: number, val: any, prev: PState | null) {
    this.sid = sid;
    this.val = val;
    this.prev = prev;
  }
}

const getstate = (state: PState | null, sid: number) => {
  while (state !== null) {
    if (state.sid === sid) {
      return state;
    }
    state = state.prev;
  }
  return state;
}

const pSymbol = (pf: PFunc, sid: number) => {
  return (px: PContext) => {
    const pos = px.pos;
    if (pf(px)) {
      px.state = new PState(sid, px.x.substring(pos, px.pos), px.state);
      return true;
    }
    return false;
  }
}

const pScope = (pf: PFunc) => {
  return (px: PContext) => {
    const state = px.state;
    if (pf(px)) {
      px.state = state;
      return true;
    }
    return false;
  }
}

const pExists = (sid: number) => {
  return (px: PContext) => {
    return getstate(px.state, sid) !== null;
  }
}

const pMatch = (sid: number) => {
  return (px: PContext) => {
    const state = getstate(px.state, sid);
    if (state !== null && px.x.startsWith(state.val, px.pos)) {
      px.pos += state.val.length;
      return true;
    }
    return false;
  }
}

const pDef = (name: string, pf: PFunc) => {
  return (px: PContext) => {
    const pos = px.pos
    if (pf(px)) {
      const s = px.x.substring(pos, px.pos);
      if (s.length === 0) {
        return true;
      }
      const ss: string[] = (px as any)[name] || [];
      ss.push(s)
      ss.sort((x, y) => x.length - y.length);
      (px as any)[name] = ss;
      console.log('@TODO ss');
      return true;
    }
    return false;
  }
}

const pIn = (name: string) => {
  return (px: PContext) => {
    const ss = (px as any)[name]
    if (ss) {
      for (const s of ss) {
        if (px.x.startsWith(s, px.pos)) {
          px.pos += s.length;
          return true;
        }
      }
    }
    return false;
  }
}



// Optimized

const pAndChar = (text: string) => {
  return (px: PContext) => {
    return px.x.startsWith(text, px.pos);
  };
}

const pNotChar = (text: string) => {
  return (px: PContext) => {
    return !px.x.startsWith(text, px.pos);
  };
}

const pOptionChar = (text: string) => {
  const clen = text.length;
  return (px: PContext) => {
    if (px.x.startsWith(text, px.pos)) {
      px.pos += clen;
    }
    return true;
  };
}

const pManyChar = (text: string) => {
  const clen = text.length;
  return (px: PContext) => {
    while (px.x.startsWith(text, px.pos)) {
      px.pos += clen;
    }
    return true;
  };
}

const pMany1Char = (text: string) => {
  const clen = text.length;
  return (px: PContext) => {
    if (!px.x.startsWith(text, px.pos)) {
      return false;
    }
    px.pos += clen;
    while (px.x.startsWith(text, px.pos)) {
      px.pos += clen;
    }
    return true;
  };
}

const pAndRange = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    return (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap));
  }
}

const pNotRange = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    return !(px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap));
  }
}

const pOptionRange = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    if (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap)) {
      px.pos += 1;
    }
    return true;
  }
}

const pManyRange = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    while (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap)) {
      px.pos += 1;
    }
    return true;
  }
}

const pMany1Range = (chars: string, ranges = '') => {
  const bitmap = toBitmap(chars, ranges);
  return (px: PContext) => {
    if (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap)) {
      px.pos += 1;
      while (px.pos < px.epos && bitmatch(px.x.charCodeAt(px.pos), bitmap)) {
        px.pos += 1;
      }
      return true;
    }
    return false;
  }
}

// ParseTree

export class ParseTree {
  static readonly EMPTY: ParseTree[] = [];
  tag_: string;
  inputs_: string;
  spos_: number;
  epos_: number;
  urn_: string;
  subs_: ParseTree[];

  public constructor(tag: string, inputs: string, spos = 0, epos = -1, urn = '(unknown source)') {
    this.tag_ = tag
    this.inputs_ = inputs
    this.spos_ = spos
    this.epos_ = (epos === -1) ? (inputs.length - spos) : epos
    this.urn_ = urn
    this.subs_ = ParseTree.EMPTY;
  }

  public is(tag: string) {
    return this.tag_ === tag;
  }

  public gettag() {
    return this.tag_;
  }

  public add(t: ParseTree, edge: string = '') {
    if (edge === '') {
      if (this.subs_ === ParseTree.EMPTY) {
        this.subs_ = [];
      }
      this.subs_.push(t)
    }
    else {
      (this as any)[edge] = t;
    }
  }

  public get(key: string) {
    return (this as any)[key];
  }

  public subNodes() {
    return this.subs_;
  }

  public isSyntaxError() {
    return this.tag_ === 'err'
  }

  private pos_(pos: number) {
    const s = this.inputs_;
    pos = Math.min(pos, s.length);
    var row = 0;
    var col = 0;
    for (var i = 0; i <= pos; i += 1) {
      if (s.charCodeAt(i) == 10) {
        row += 1;
        col = 0;
      }
      else {
        col += 1;
      }
    }
    return [pos, row, col]
  }

  public beginPosition() {
    return this.pos_(this.spos_);
  }

  public endPosition() {
    return this.pos_(this.spos_);
  }

  public length() {
    return this.epos_ - this.spos_;
  }

  public keys() {
    return Object.keys(this).filter(x => !x.endsWith('_'));
  }

  public toString() {
    return this.inputs_.substring(this.spos_, this.epos_);
  }

  public dump() {
    const sb: string[] = [];
    this.strOut(sb);
    return sb.join('');
  }

  protected strOut(sb: string[]) {
    var c = 0;
    sb.push("[#")
    sb.push(this.tag_)
    for (const node of this.subNodes()) {
      c += 1;
      sb.push(` `);
      node.strOut(sb);
    }
    for (const key of this.keys()) {
      sb.push(` ${key} = `);
      (this as any)[key].strOut(sb);
    }
    if (c == 0) {
      sb.push(' ');
      sb.push(quote(this.inputs_.substring(this.spos_, this.epos_)))
    }
    sb.push("]")
  }

  public showing(msg = 'Syntax Error') {
    const p = this.beginPosition();
    const pos = p[0];
    const row = p[1];
    const col = p[2];
    return `(${this.urn_}:${row}+${col}) ${msg}`
  }
}

const PTree2ParseTree = (pt: PTree, urn: string, inputs: string) => {
  if (pt.prev !== null) {
    return PTree2ParseTreeChild('', urn, inputs, pt.spos, pt.epos, pt)
  }
  else {
    return PTree2ParseTreeChild(pt.tag, urn, inputs, pt.spos, pt.epos, pt.child)
  }
}

const PTree2ParseTreeChild = (tag: string, urn: string, inputs: string, spos: number, epos: number, sub: PTree | null) => {
  const t = new ParseTree(tag, inputs, spos, epos, urn);
  while (sub !== null) {
    if (sub.isEdge()) {
      if (sub.child === null) {
        var tt = PTree2ParseTreeChild('', urn, inputs, sub.spos, Math.abs(sub.epos), null)
      }
      else {
        tt = PTree2ParseTree(sub.child, urn, inputs);
      }
      t.add(tt, sub.tag);
    }
    else {
      t.add(PTree2ParseTreeChild(sub.tag, urn, inputs,
        sub.spos, sub.epos, sub.child))
    }
    sub = sub.prev;
  }
  const tail = t.subs_.length - 1
  for (var i = 0; i < (tail + 1) / 2; i += 1) {
    const t0 = t.subs_[i];
    t.subs_[i] = t.subs_[tail - i]
    t.subs_[tail - i] = t0;
  }
  return t;
}

const translate = (s: string, dic: { [key: string]: string }) => {
  var foundESC = false;
  for (const c of Object.keys(dic)) {
    if (s.indexOf(c) !== -1) {
      foundESC = true;
      break;
    }
  }
  if (foundESC) {
    const sb = []
    for (const c of s) {
      if (c in dic) {
        sb.push(dic[c]);
      }
      else {
        sb.push(c);
      }
    }
    return sb.join('')
  }
  return s;
}

const ESCTBL = { '\n': '\\n', '\t': '\\t', '\r': '\\r', '\v': '\\v', '\f': '\\f', '\\': '\\\\', "'": "\\'" }

export const quote = (s: string) => {
  return "'" + translate(s, ESCTBL) + "'"
}

export type Parser = (inputs: string, options?: any) => ParseTree;

export class PAsm {

  public static pRule = (peg: { [key: string]: PFunc }, name: string, e: PFunc) => {
    peg[name] = e;
  }

  public static pEmpty = pEmpty;
  public static pFail = pFail;
  public static pAny = pAny;
  public static pSkip = pSkip;
  public static pChar = pChar;
  public static pRange = pRange;
  public static pRef = pRef;
  public static pMemo = pMemo;

  public static pAnd = pAnd;
  public static pNot = pNot;
  public static pMany = pMany;
  public static pMany1 = pMany1;
  public static pOption = pOption;

  public static pSeq = pSeq;
  public static pSeq2 = pSeq2;
  public static pSeq3 = pSeq3;
  public static pSeq4 = pSeq4;

  public static pOre = pOre;
  public static pOre2 = pOre2;
  public static pOre3 = pOre3;
  public static pOre4 = pOre4;
  public static pDict = pDict;

  public static pNode = pNode;
  public static pEdge = pEdge;
  public static pFold = pFold;
  public static pAbs = pAbs;

  /* Symbol */
  public static pSymbol = pSymbol;
  public static pScope = pScope;
  public static pExists = pExists;
  public static pMatch = pMatch;

  /* Optimize */

  public static pAndChar = pAndChar;
  public static pNotChar = pNotChar;
  public static pOptionChar = pOptionChar;
  public static pManyChar = pManyChar;
  public static pMany1Char = pMany1Char;

  public static pAndRange = pAndRange;
  public static pNotRange = pNotRange;
  public static pOptionRange = pOptionRange;
  public static pManyRange = pManyRange;
  public static pMany1Range = pMany1Range;

  public static pDef = pDef;
  public static pIn = pIn;

  public static generate = (generated: { [key: string]: PFunc }, start: string): Parser => {
    const pf = generated[start];
    return (inputs: string, options?: any) => {
      options = options || {};
      const pos: number = options.pos || options.spos || 0;
      const epos: number = options.epos || (inputs.length - pos);
      const px = new PContext(inputs, pos, epos);
      if (pf(px)) {
        if (!px.ast) {
          px.ast = new PTree(null, "", pos, px.pos, null);
        }
      }
      else {
        px.ast = new PTree(null, "err", px.headpos, px.headpos, null);
      }
      const conv: ((t: PTree, urn: string, inputs: string) => ParseTree) = options.conv || PTree2ParseTree;
      const urn = options.urn || '(unknown source)';
      return conv(px.ast!, urn, inputs);
    }
  }

  public static example = (generated: { [key: string]: PFunc }, start: string, input: string) => {
    const p = PAsm.generate(generated, start);
    const t = p(input)
    console.log(t.dump())
  }

}

