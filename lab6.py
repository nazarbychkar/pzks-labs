"""ЛР6, варіант 23 (матрична система, 9 ПЕ, тор 3x3): вибір оптимальної форми виразу.
Будуються еквівалентні форми, кожна моделюється (lab5.simulate), обирається найкраща.
Запуск: python lab6.py "a-b*(k-t)-(f-g)*(f-5.9-q)-(f+g)/(d+q-w)" [--tc 1] [--times "+=1,*=2,/=4"]"""
import argparse
from fractions import Fraction
from lab1 import ExpressionAnalyzer
from lab2 import Parser, tokenize, simplify, flatten, build, collect, to_str, fmt_num, Node, DivZero
import lab5


def seq(n):
    """Послідовне (ліво-асоціативне) дерево без балансування."""
    if n[0] == 'num':
        return Node(label=fmt_num(n[1]), value=n[1])
    if n[0] == 'var':
        return Node(label=n[1])
    items = sorted(((sg, seq(t)) for sg, t in n[1]), key=lambda x: x[0] < 0)
    plus, minus = ('+', '-') if n[0] == 'sum' else ('*', '/')
    sg0, acc = items[0]
    if sg0 < 0:
        acc = Node('neg', acc) if n[0] == 'sum' else Node('/', Node(label='1', value=Fraction(1)), acc)
    for sg, t in items[1:]:
        acc = Node(plus if sg > 0 else minus, acc, t)
    return acc


def expand(n):
    """Розкриття дужок (дистрибутивність): сума добутків. Дільники-суми не розкриваються."""
    def ex(n):
        if n[0] == 'sum':
            return [(sg * s2, f) for sg, t in n[1] for s2, f in ex(t)]
        if n[0] == 'prod':
            acc = [(1, [])]
            for e, t in n[1]:
                if e > 0:
                    acc = [(s1 * s2, f1 + f2) for s1, f1 in acc for s2, f2 in ex(t)]
                else:
                    acc = [(s1, f1 + [(-1, t)]) for s1, f1 in acc]
            return acc
        return [(1, [(1, n)])]
    nodes = [(sg, fs[0][1] if len(fs) == 1 and fs[0][0] == 1 else ('prod', fs)) for sg, fs in ex(n)]
    return nodes[0][1] if len(nodes) == 1 and nodes[0][0] == 1 else ('sum', nodes)


def sig(n):
    return n.label if n.op is None else f"({sig(n.l)}{n.op}{sig(n.r) if n.r else ''})"


def make_forms(ast):
    makers = [("Послідовна (без балансування)", lambda: (flatten(ast), seq)),
              ("Збалансована, без спрощення", lambda: (flatten(ast), build)),
              ("Збалансована, спрощена (ЛР2)", lambda: (simplify(ast), build)),
              ("Розкриття дужок + спрощення", lambda: (simplify(expand(ast)), build))]
    forms, seen = [], set()
    for name, mk in makers:
        try:
            a, builder = mk()
        except DivZero as e:
            print(f"  [{name}] пропущено: ділення на нуль ('{e.divisor}')")
            continue
        root = builder(a)
        if sig(root) not in seen:
            seen.add(sig(root))
            forms.append((name, to_str(a), root))
    return forms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('expr')
    ap.add_argument('--tc', type=int, default=1)
    ap.add_argument('--times', default="")
    a = ap.parse_args()
    for kv in filter(None, a.times.split(',')):
        k, v = kv.split('=')
        lab5.T[k.strip()] = int(v)

    an = ExpressionAnalyzer(a.expr)
    an.analyze()
    if an.errors:
        return print("Вираз некоректний:", *[e.message for e in an.errors], sep="\n  - ")
    forms = make_forms(Parser(tokenize(a.expr)).parse())

    rows = []
    for name, text, root in forms:
        ops, _ = collect(root)
        if not ops:
            continue
        lv = {}
        for o in ops:
            lv[o.level] = lv.get(o.level, 0) + 1
        sched, T1, Tp = lab5.simulate(root, a.tc)
        rows.append(dict(name=name, text=text, root=root, sched=sched, n=len(ops), h=root.level,
                         w=max(lv.values()), T1=T1, Tp=Tp, S=T1 / Tp, E=T1 / Tp / lab5.P))
    if not rows:
        return print("У виразі немає операцій.")

    print(f"Вираз: {a.expr}\nСистема: матрична, P={lab5.P}, тор {lab5.R}x{lab5.C}, tc={a.tc}, час операцій {lab5.T}\n")
    print(f"{'№':>2} {'Форма':<32}{'Опер.':>6}{'Вис.':>5}{'Шир.':>5}{'T1':>5}{'Tp':>5}{'S':>7}{'E':>7}")
    best = min(rows, key=lambda r: (r['Tp'], r['T1']))
    for i, r in enumerate(rows, 1):
        mark = '  <-- оптимальна' if r is best else ''
        print(f"{i:>2} {r['name']:<32}{r['n']:>6}{r['h']:>5}{r['w']:>5}{r['T1']:>5}{r['Tp']:>5}{r['S']:>7.2f}{r['E']:>7.2f}{mark}")
    print("\nФорми:")
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['text']}")

    print(f"\nОптимальна форма: {best['name']}\n")
    lab5.print_schedule(best['sched'])

    print("\nВплив часу передачі tc (найкраща форма):")
    for tc in range(4):
        res = [(lab5.simulate(r['root'], tc)[2], i) for i, r in enumerate(rows, 1)]
        tp, i = min(res)
        print(f"  tc={tc}: форма №{i}, Tp={tp}")


if __name__ == '__main__':
    main()