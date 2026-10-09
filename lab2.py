import sys
import re
import heapq
import itertools
from fractions import Fraction
from decimal import Decimal

# 1. Імпортуємо аналізатор з першої лабораторної роботи (lab1.py)
try:
    from lab1 import ExpressionAnalyzer
except ImportError:
    print("Помилка: Не знайдено файл lab1.py в поточній директорії!")
    sys.exit(1)


# ───────────────────────────── Лексика / розбір (ЛР2) ─────────────────────────────
TOKEN_RE = re.compile(r'\s*(?:(\d+\.\d*|\.\d+|\d+)|([A-Za-z_][A-Za-z_0-9]*)|(\S))')


class ParseError(Exception):
    pass


class DivZero(Exception):
    def __init__(self, divisor):
        super().__init__(divisor)
        self.divisor = divisor


def tokenize(s):
    toks, pos, s = [], 0, s.rstrip()
    while pos < len(s):
        m = TOKEN_RE.match(s, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            toks.append(('num', m.group(1)))
        elif m.group(2):
            toks.append(('id', m.group(2)))
        else:
            toks.append(('op', m.group(3)))
    return toks


# AST: ('num', Fraction) | ('var', str) | ('sum', [(±1, node)]) | ('prod', [(±1, node)])
class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ('end', '')

    def eat(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        n = self.expr()
        if self.peek()[0] != 'end':
            raise ParseError(f"неочікуваний токен '{self.peek()[1]}'")
        return n

    def expr(self):
        items = [(1, self.term())]
        while self.peek() in (('op', '+'), ('op', '-')):
            op = self.eat()[1]
            items.append((1 if op == '+' else -1, self.term()))
        return items[0][1] if len(items) == 1 else ('sum', items)

    def term(self):
        items = [(1, self.factor())]
        while self.peek() in (('op', '*'), ('op', '/')):
            op = self.eat()[1]
            items.append((1 if op == '*' else -1, self.factor()))
        return items[0][1] if len(items) == 1 else ('prod', items)

    def factor(self):
        k, v = self.eat()
        if k == 'num':
            return ('num', Fraction(v))
        if k == 'id':
            return ('var', v)
        if (k, v) == ('op', '('):
            n = self.expr()
            if self.eat() != ('op', ')'):
                raise ParseError("очікувалась ')'")
            return n
        if (k, v) in (('op', '-'), ('op', '+')):
            n = self.factor()
            return ('sum', [(-1, n)]) if v == '-' else n
        raise ParseError(f"неочікуваний токен '{v}'" if k != 'end' else "неочікуваний кінець виразу")


# ───────────────────────────── Допоміжне: вивід ─────────────────────────────
def fmt_num(q):
    if q.denominator == 1:
        return str(q.numerator)
    d = q.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d == 1:
        s = format(Decimal(q.numerator) / Decimal(q.denominator), 'f')
        return s.rstrip('0').rstrip('.') if '.' in s else s
    return f"{q.numerator}/{q.denominator}"


def to_str(n, wrap=False):
    k = n[0]
    if k == 'num':
        s = fmt_num(n[1])
        return f"({s})" if wrap and ('/' in s or n[1] < 0) else s
    if k == 'var':
        return n[1]
    if k == 'sum':
        s = ''
        for i, (sg, t) in enumerate(n[1]):
            ts = to_str(t, wrap=(sg < 0 and t[0] == 'sum'))
            if i == 0:
                s = ('-' if sg < 0 else '') + ts
            else:
                s += (' - ' if sg < 0 else ' + ') + ts
        return f"({s})" if wrap else s
    s = ''
    for i, (e, t) in enumerate(n[1]):
        w = t[0] == 'sum' or (e < 0 and t[0] == 'prod') or (i > 0 and t[0] == 'num')
        ts = to_str(t, wrap=w)
        s = ts if i == 0 else s + ('*' if e > 0 else '/') + ts
    return f"({s})" if wrap else s


# ───────────────────── Розкриття дужок (+/-) і зняття зайвих ─────────────────────
def flatten(n):
    k = n[0]
    if k not in ('sum', 'prod'):
        return n
    items = []
    for sg, t in n[1]:
        c = flatten(t)
        if c[0] == k:
            items += [(sg * s2, x) for s2, x in c[1]]
        else:
            items.append((sg, c))
    return items[0][1] if len(items) == 1 and items[0][0] == 1 else (k, items)


# ───────────────────────────── Спрощення ─────────────────────────────
def key(n):
    k = n[0]
    if k == 'num':
        return '#' + str(n[1])
    if k == 'var':
        return n[1]
    parts = sorted(('+' if s > 0 else '-') + key(t) for s, t in n[1])
    return ('S(' if k == 'sum' else 'P(') + ','.join(parts) + ')'


def key_of(fs):
    return ','.join(sorted(('+' if e > 0 else '-') + key(f) for e, f in fs))


def split_coef(n):
    if n[0] == 'num':
        return n[1], []
    if n[0] == 'prod':
        c, fs = Fraction(1), []
        for e, f in n[1]:
            if f[0] == 'num':
                c = c * f[1] if e == 1 else c / f[1]
            else:
                fs.append((e, f))
        return c, fs
    return Fraction(1), [(1, n)]


def simplify(n):
    k = n[0]
    if k == 'sum':
        return simp_sum(n[1])
    if k == 'prod':
        return simp_prod(n[1])
    return n


def simp_sum(terms):
    const = Fraction(0)
    groups = {}

    def add(sg, n):
        nonlocal const
        if n[0] == 'sum':
            for s2, t in n[1]:
                add(sg * s2, t)
            return
        c, fs = split_coef(n)
        if not fs:
            const += sg * c
            return
        k = key_of(fs)
        if k in groups:
            groups[k][0] += sg * c
        else:
            groups[k] = [sg * c, fs]

    for sg, t in terms:
        add(sg, simplify(t))

    items = []
    for c, fs in groups.values():
        if c == 0:
            continue
        sg, m = (1 if c > 0 else -1), abs(c)
        factors = ([(1, ('num', m))] if m != 1 else []) + fs
        if not any(e > 0 for e, _ in factors):
            factors.insert(0, (1, ('num', Fraction(1))))
        node = factors[0][1] if len(factors) == 1 else ('prod', factors)
        items.append((sg, node))
    if not items:
        return ('num', const)
    if const != 0:
        items.append((1 if const > 0 else -1, ('num', abs(const))))
    return items[0][1] if len(items) == 1 and items[0][0] == 1 else ('sum', items)


def simp_prod(factors):
    const = Fraction(1)
    items = []

    def add(e, n, orig=None):
        nonlocal const
        k = n[0]
        if k == 'prod':
            for e2, f in n[1]:
                add(e * e2, f)
        elif k == 'num':
            if e == 1:
                const *= n[1]
            elif n[1] == 0:
                raise DivZero(to_str(orig if orig is not None else n))
            else:
                const /= n[1]
        else:
            items.append((e, n))

    for e, t in factors:
        add(e, simplify(t), t)
    if const == 0:
        return ('num', Fraction(0))
    net = {}
    for e, n in items:
        k = key(n)
        if k in net:
            net[k][0] += e
        else:
            net[k] = [e, n]
    pos, neg = [], []
    for c, n in net.values():
        (pos if c > 0 else neg).extend([n] * abs(c))
    if const != 1:
        pos.insert(0, ('num', const))
    if not pos and not neg:
        return ('num', Fraction(1))
    if not pos:
        pos = [('num', Fraction(1))]
    if not neg and len(pos) == 1:
        return pos[0]
    return ('prod', [(1, n) for n in pos] + [(-1, n) for n in neg])


# ───────────────────────────── Дерево паралельної форми ─────────────────────────────
class Node:
    def __init__(self, op=None, l=None, r=None, label='', value=None):
        self.op, self.l, self.r, self.label, self.value = op, l, r, label, value
        self.level = 0 if op is None else 1 + max(l.level, r.level if r else 0)
        self.id = None


def build(n):
    k = n[0]
    if k == 'num':
        return Node(label=fmt_num(n[1]), value=n[1])
    if k == 'var':
        return Node(label=n[1])
    items = [(sg, build(t)) for sg, t in n[1]]
    return combine(items, '+', '-') if k == 'sum' else combine(items, '*', '/')


def combine(items, plus, minus):
    cnt = itertools.count()
    heap = [(t.level, next(cnt), sg, t) for sg, t in items]
    heapq.heapify(heap)
    while len(heap) > 1:
        _, _, sa, a = heapq.heappop(heap)
        _, _, sb, b = heapq.heappop(heap)
        if sa < 0 < sb:
            sa, a, sb, b = sb, b, sa, a
        if sa > 0 and sb > 0:
            node, sg = Node(plus, a, b), 1
        elif sa > 0 > sb:
            node, sg = Node(minus, a, b), 1
        else:
            node, sg = Node(plus, a, b), -1
        heapq.heappush(heap, (node.level, next(cnt), sg, node))
    _, _, sg, t = heap[0]
    if sg < 0:
        if plus == '+':
            return Node('neg', t)
        return Node('/', Node(label='1', value=Fraction(1)), t)
    return t


def collect(root):
    ops, leaves = [], []

    def rec(n):
        if n.op is None:
            leaves.append(n)
            return
        rec(n.l)
        if n.r:
            rec(n.r)
        ops.append(n)

    rec(root)
    ops.sort(key=lambda x: x.level)
    for i, o in enumerate(ops, 1):
        o.id = i
    return ops, leaves


def name(n):
    return n.label if n.op is None else f"t{n.id}"


def formula(o):
    if o.op == 'neg':
        return f"t{o.id} = -{name(o.l)}"
    return f"t{o.id} = {name(o.l)} {o.op} {name(o.r)}"


def evaluate(n):
    if n.op is None:
        if n.value is None:
            raise ValueError("змінна без значення")
        return n.value
    a = evaluate(n.l)
    if n.op == 'neg':
        return -a
    b = evaluate(n.r)
    return {'+': a + b, '-': a - b, '*': a * b, '/': None}[n.op] if n.op != '/' else a / b


def draw(n, prefix='', last=True, root=True, out=None):
    text = n.label if n.op is None else f"{n.op}  [t{n.id}, ярус {n.level}]"
    out.append(text if root else prefix + ('└─ ' if last else '├─ ') + text)
    kids = [c for c in (n.l, n.r) if c is not None]
    for i, c in enumerate(kids):
        draw(c, '' if root else prefix + ('   ' if last else '│  '), i == len(kids) - 1, False, out)


# ───────────────────────────── Головний пайплайн ─────────────────────────────
def process(expr, do_simplify=True, show_tree=False, quiet=False):
    if not quiet:
        print(f"Вираз: {expr}")

    # --- ЕТАП 1: Перевірка ЛР1 ---
    analyzer = ExpressionAnalyzer(expr)
    analyzer.analyze()

    if analyzer.errors:
        if not quiet:
            print("\n[ЛР1] Знайдено синтаксичні/лексичні помилки:")
            analyzer.print_report()
            print("\nОбробку зупинено: побудова дерева ЛР2 неможлива для некоректного виразу.\n")
        return {'errors': [e.message for e in analyzer.errors]}

    if not quiet:
        print("[ЛР1] Вираз коректний. Переходимо до ЛР2...\n")

    # --- ЕТАП 2: Побудова дерева ЛР2 ---
    try:
        ast = Parser(tokenize(expr)).parse()
    except ParseError as e:
        print(f"[ЛР2 ParseError]: {e}")
        return {'errors': [str(e)]}

    if do_simplify:
        errs = []
        terms = ast[1] if ast[0] == 'sum' else [(1, ast)]
        for i, (_, t) in enumerate(terms, 1):
            try:
                simplify(t)
            except DivZero as e:
                errs.append(f"терм #{i} '{to_str(t)}': ділення на нуль, дільник '{e.divisor}' = 0")
        if errs:
            if not quiet:
                for e in errs:
                    print("  ПОМИЛКА ЛР2:", e)
            return {'errors': errs}
        ast = simplify(ast)
    else:
        ast = flatten(ast)

    root = build(ast)
    ops, leaves = collect(root)
    height = root.level
    levels = {}
    for o in ops:
        levels.setdefault(o.level, []).append(o)
    width = max((len(v) for v in levels.values()), default=0)
    res = {'form': to_str(ast), 'height': height, 'width': width, 'ops': len(ops), 'root': root, 'errors': []}

    if not quiet:
        print(f"Після розкриття дужок{' та спрощення' if do_simplify else ''}: {res['form']}")
        print(f"Ярус 0 (операнди): {' '.join(l.label for l in leaves)}")
        for lv in sorted(levels):
            print(f"Ярус {lv} ({len(levels[lv])} оп.): " + ' | '.join(formula(o) for o in levels[lv]))
        n = len(ops)
        if height:
            print(f"\nВисота: {height}  Ширина: {width}  Операцій: {n}  "
                  f"Прискорення S=n/h={n / height:.2f}  Ефективність E=S/p={n / height / width:.2f}")
        if show_tree:
            print("\nДерево розбору:")
            out = []
            draw(root, out=out)
            print('\n'.join(out))
        print("=" * 60 + "\n")
    return res


def main():
    args = sys.argv[1:]
    tree = '--tree' in args
    raw = '--raw' in args
    exprs = [a for a in args if not a.startswith('--')]

    if not exprs:
        print("Введіть вираз (порожній рядок - вихід):")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                break
            process(line, not raw, tree)
        return

    for ex in exprs:
        process(ex, not raw, tree)


if __name__ == '__main__':
    main()