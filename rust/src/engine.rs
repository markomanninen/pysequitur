//! The Sequitur engine of `pysequitur/core.py`, ported function by function.
//!
//! It must build exactly the grammar of the Python engine, which builds that of
//! Nevill-Manning's C++ reference, so every function below keeps the order in
//! which the Python one reads and writes links and the digram index. Where the
//! Python code holds on to a symbol that a nested call may have unlinked, this
//! code does too: symbols live in an arena and are never freed or reused, so a
//! stale symbol keeps the links it had when it was unlinked, as a Python object
//! that is still referenced does.
//!
//! Values: a terminal is its token id (below `MAX_ID`); a nonterminal and a
//! guard are `RULE | rule number`. As in the Python engine, where both carry
//! the Rule object as their value, a guard and a reference to its rule have the
//! same value. A symbol keeps its value and a guard flag in one word.

use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};

pub const NIL: u32 = u32::MAX;
pub const RULE: u32 = 1 << 31;
const GUARD: u32 = 1 << 30;
/// Token ids and rule numbers are below this.
pub const MAX_ID: u32 = GUARD;

/// Multiplicative hash for integer keys, folded so that the low bits, which
/// pick the bucket, depend on both halves of a digram key.
#[derive(Default, Clone, Copy)]
pub struct IntHasher(u64);

impl Hasher for IntHasher {
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }

    #[inline]
    fn write(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.write_u64(b as u64);
        }
    }

    #[inline]
    fn write_u64(&mut self, x: u64) {
        let h = (self.0 ^ x).wrapping_mul(0x9E37_79B9_7F4A_7C15);
        self.0 = h ^ (h >> 32);
    }

    #[inline]
    fn write_u32(&mut self, x: u32) {
        self.write_u64(x as u64)
    }

    #[inline]
    fn write_i64(&mut self, x: i64) {
        self.write_u64(x as u64)
    }
}

pub type IntMap<K, V> = HashMap<K, V, BuildHasherDefault<IntHasher>>;

#[derive(Clone, Copy)]
struct Sym {
    prev: u32,
    next: u32,
    /// the value, with GUARD set on guards
    word: u32,
}

impl Sym {
    #[inline]
    fn value(&self) -> u32 {
        self.word & !GUARD
    }

    #[inline]
    fn is_guard(&self) -> bool {
        self.word & GUARD != 0
    }
}

#[derive(Clone, Copy)]
struct Rule {
    guard: u32,
    refs: i64,
}

#[inline]
fn key(left: u32, right: u32) -> u64 {
    ((left as u64) << 32) | right as u64
}

/// The rule a value stands for: `symbol.rule` in the Python engine, which is
/// set for nonterminals and guards and None for terminals.
#[inline]
fn rule_of(value: u32) -> Option<usize> {
    if value & RULE != 0 {
        Some((value & !RULE) as usize)
    } else {
        None
    }
}

pub struct Engine {
    syms: Vec<Sym>,
    rules: Vec<Rule>,
    index: IntMap<u64, u32>,
    length: u64,
}

impl Default for Engine {
    fn default() -> Self {
        Self::new()
    }
}

impl Engine {
    pub fn new() -> Self {
        let mut e = Engine {
            syms: Vec::new(),
            rules: Vec::new(),
            index: IntMap::default(),
            length: 0,
        };
        e.new_rule(); // the root, rule 0
        e
    }

    /// Number of tokens read so far.
    pub fn len(&self) -> u64 {
        self.length
    }

    /// Make room for the symbols and digrams of `tokens` more tokens. Each
    /// token is one symbol, and every rule made on the way takes four more (a
    /// guard, two copies and a reference); the 1.6 MB benchmark input takes 2.1
    /// symbols a token. Room that is never written stays virtual memory.
    pub fn reserve(&mut self, tokens: usize) {
        self.syms.reserve(tokens * 5 / 2);
        // a long input has far fewer distinct digrams than tokens
        self.index.reserve(tokens.min(1 << 16));
    }

    #[inline]
    fn s(&self, i: u32) -> &Sym {
        &self.syms[i as usize]
    }

    #[inline]
    fn s_mut(&mut self, i: u32) -> &mut Sym {
        &mut self.syms[i as usize]
    }

    #[inline]
    fn value(&self, i: u32) -> u32 {
        self.s(i).value()
    }

    #[inline]
    fn next(&self, i: u32) -> u32 {
        self.s(i).next
    }

    #[inline]
    fn prev(&self, i: u32) -> u32 {
        self.s(i).prev
    }

    #[inline]
    fn is_guard(&self, i: u32) -> bool {
        self.s(i).is_guard()
    }

    #[inline]
    fn new_symbol(&mut self, value: u32) -> u32 {
        let i = self.syms.len();
        assert!(i < NIL as usize, "more than 2^32 - 1 symbols");
        self.syms.push(Sym {
            prev: NIL,
            next: NIL,
            word: value,
        });
        i as u32
    }

    /// `del index[key]` if the index holds `symbol` under it.
    #[inline]
    fn unindex(&mut self, k: u64, symbol: u32) {
        if let std::collections::hash_map::Entry::Occupied(e) = self.index.entry(k) {
            if *e.get() == symbol {
                e.remove();
            }
        }
    }

    /// Append one token, given by its id.
    pub fn stream(&mut self, token: u32) {
        let guard = self.rules[0].guard;
        let last = self.prev(guard);
        let symbol = self.new_symbol(token);
        self.insert_after(last, symbol);
        self.length += 1;
        if self.length > 1 {
            let p = self.prev(self.prev(guard));
            self.check(p);
        }
    }

    pub fn feed(&mut self, tokens: &[u32]) {
        self.reserve(tokens.len());
        for &t in tokens {
            self.stream(t);
        }
    }

    /// The rules in the order of `Grammar.rules()`: the main rule first, the
    /// others in order of first use. Each rule's symbols go to `items` (token
    /// ids, or `RULE | position of the rule in this order`), and `ends` gets the
    /// end of each rule in `items`.
    pub fn rules(&self, items: &mut Vec<u32>, ends: &mut Vec<usize>) {
        let mut number = vec![NIL; self.rules.len()];
        let mut order: Vec<usize> = vec![0];
        number[0] = 0;
        let mut k = 0;
        while k < order.len() {
            let rule = order[k];
            let mut s = self.next(self.rules[rule].guard);
            while !self.is_guard(s) {
                let v = self.value(s);
                match rule_of(v) {
                    None => items.push(v),
                    Some(r) => {
                        if number[r] == NIL {
                            number[r] = order.len() as u32;
                            order.push(r);
                        }
                        items.push(RULE | number[r]);
                    }
                }
                s = self.next(s);
            }
            ends.push(items.len());
            k += 1;
        }
    }

    /// Total number of symbols on the right-hand sides of the rules that
    /// `rules()` returns: `sum(len(r) for r in rules())`.
    pub fn size(&self) -> (usize, usize) {
        let mut seen = vec![false; self.rules.len()];
        let mut todo = vec![0usize];
        seen[0] = true;
        let mut symbols = 0;
        let mut rules = 0;
        while let Some(rule) = todo.pop() {
            rules += 1;
            let mut s = self.next(self.rules[rule].guard);
            while !self.is_guard(s) {
                symbols += 1;
                if let Some(r) = rule_of(self.value(s)) {
                    if !seen[r] {
                        seen[r] = true;
                        todo.push(r);
                    }
                }
                s = self.next(s);
            }
        }
        (rules, symbols)
    }

    /// The main rule expanded to token ids: the input read so far.
    pub fn expand(&self) -> Vec<u32> {
        let mut out = Vec::with_capacity(self.length as usize);
        let mut stack: Vec<u32> = Vec::new();
        let mut s = self.next(self.rules[0].guard);
        loop {
            if self.is_guard(s) {
                match stack.pop() {
                    Some(n) => {
                        s = n;
                        continue;
                    }
                    None => break,
                }
            }
            let v = self.value(s);
            match rule_of(v) {
                None => {
                    out.push(v);
                    s = self.next(s);
                }
                Some(r) => {
                    stack.push(self.next(s));
                    s = self.next(self.rules[r].guard);
                }
            }
        }
        out
    }

    // The algorithm, in the order of pysequitur/core.py.

    fn new_rule(&mut self) -> usize {
        let r = self.rules.len();
        assert!(r < MAX_ID as usize, "more than 2^30 rules");
        let g = self.syms.len();
        assert!(g < NIL as usize, "more than 2^32 - 1 symbols");
        let g = g as u32;
        self.syms.push(Sym {
            prev: g,
            next: g,
            word: RULE | GUARD | r as u32,
        });
        self.rules.push(Rule { guard: g, refs: 0 });
        r
    }

    /// Link two symbols, removing the digram they used to start from the index.
    fn join(&mut self, left: u32, right: u32) {
        let old = self.next(left);
        if old != NIL {
            let l = *self.s(left);
            let o = *self.s(old);
            if !(l.is_guard() || o.is_guard()) {
                self.unindex(key(l.value(), o.value()), left);
            }
            // In a triple such as 'bbb' only the second digram is indexed. When
            // it is broken up, index the first so that it is not forgotten.
            let r = *self.s(right);
            let (rp, rn) = (r.prev, r.next);
            if rp != NIL && rn != NIL {
                let rnv = self.value(rn);
                if r.value() == self.value(rp) && r.value() == rnv {
                    self.index.insert(key(r.value(), rnv), right);
                }
            }
            let lp = self.prev(left);
            if lp != NIL {
                let lpv = self.value(lp);
                if l.value() == o.value() && l.value() == lpv {
                    self.index.insert(key(lpv, l.value()), lp);
                }
            }
        }
        self.s_mut(left).next = right;
        self.s_mut(right).prev = left;
    }

    fn insert_after(&mut self, left: u32, symbol: u32) {
        let n = self.next(left);
        self.join(symbol, n);
        self.join(left, symbol);
    }

    fn delete(&mut self, symbol: u32) {
        let (p, n) = (self.prev(symbol), self.next(symbol));
        self.join(p, n);
        let following = self.next(symbol);
        if !self.is_guard(following) {
            let k = key(self.value(symbol), self.value(following));
            self.unindex(k, symbol);
        }
        if let Some(r) = rule_of(self.value(symbol)) {
            self.rules[r].refs -= 1;
        }
    }

    fn reference(&mut self, rule: usize) -> u32 {
        self.rules[rule].refs += 1;
        self.new_symbol(RULE | rule as u32)
    }

    fn copy(&mut self, symbol: u32) -> u32 {
        let v = self.value(symbol);
        if let Some(r) = rule_of(v) {
            self.rules[r].refs += 1;
        }
        self.new_symbol(v)
    }

    /// Replace the digram starting at symbol with a reference to rule.
    fn substitute(&mut self, symbol: u32, rule: usize) {
        let prev = self.prev(symbol);
        let a = self.next(prev);
        self.delete(a);
        let b = self.next(prev);
        self.delete(b);
        let nt = self.reference(rule);
        self.insert_after(prev, nt);
    }

    /// Inline the rule of a nonterminal that is its last reference.
    fn expand_symbol(&mut self, symbol: u32) {
        let left = self.prev(symbol);
        let right = self.next(symbol);
        let rule = rule_of(self.value(symbol)).expect("expand on a terminal");
        let guard = self.rules[rule].guard;
        let first = self.next(guard);
        let last = self.prev(guard);
        let k = key(self.value(symbol), self.value(right));
        self.unindex(k, symbol);
        self.join(left, first);
        self.join(last, right);
        let k = key(self.value(last), self.value(self.next(last)));
        self.index.insert(k, last);
    }

    /// Index the digram starting at symbol, or deal with its earlier occurrence.
    fn check(&mut self, symbol: u32) {
        let k = key(self.value(symbol), self.value(self.next(symbol)));
        match self.index.get(&k).copied() {
            None => {
                self.index.insert(k, symbol);
            }
            Some(m) => {
                // overlapping occurrences such as 'aaa' stay
                if self.next(m) != symbol {
                    self.process_match(symbol, m);
                }
            }
        }
    }

    /// Check the digrams around a symbol after its neighbourhood changed.
    fn propagate_change(&mut self, symbol: u32) {
        let following = self.next(symbol);
        if self.is_guard(symbol) || self.is_guard(following) {
            if !(self.is_guard(following) || self.is_guard(self.next(following))) {
                self.check(following);
            }
            return;
        }
        let k = key(self.value(symbol), self.value(following));
        match self.index.get(&k).copied() {
            None => {
                self.index.insert(k, symbol);
                if !(self.is_guard(following) || self.is_guard(self.next(following))) {
                    self.check(following);
                }
            }
            Some(m) => {
                if self.next(m) != symbol {
                    self.process_match(symbol, m);
                }
            }
        }
    }

    /// Enforce digram uniqueness: the digram at symbol already occurs at m.
    fn process_match(&mut self, symbol: u32, m: u32) {
        let rule;
        let mp = self.prev(m);
        if self.is_guard(mp) && self.is_guard(self.next(self.next(m))) {
            // the earlier occurrence is a whole rule: reuse it
            rule = rule_of(self.value(mp)).expect("guard without a rule");
            self.substitute(symbol, rule);
            let p = self.prev(symbol);
            self.propagate_change(p);
        } else {
            rule = self.new_rule();
            let guard = self.rules[rule].guard;
            let last = self.prev(guard);
            let c = self.copy(symbol);
            self.insert_after(last, c);
            let last = self.prev(guard);
            let c = self.copy(self.next(symbol));
            self.insert_after(last, c);
            self.substitute(m, rule);
            let p = self.prev(m);
            self.propagate_change(p);
            // index the new rule's digram only after the first occurrence is
            // replaced, as the C++ reference does
            let first = self.next(guard);
            let k = key(self.value(first), self.value(self.next(first)));
            self.index.insert(k, first);
            self.substitute(symbol, rule);
            let p = self.prev(symbol);
            self.propagate_change(p);
        }
        // rule utility: a nested rule now used only once is inlined
        let first = self.next(self.rules[rule].guard);
        if let Some(r) = rule_of(self.value(first)) {
            if !self.is_guard(first) && self.rules[r].refs == 1 {
                self.expand_symbol(first);
            }
        }
    }
}
