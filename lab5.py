"""ЛР5, варіант 23: матрична система, 9 процесорів, топологія тор (3x3).
Запуск: python lab5.py "(a+b)+c/d+g+(k/l+m+n)" [--tc 1] [--times "+=1,-=1,*=2,/=4"]"""
import argparse
from lab2 import process

P, R, C = 9, 3, 3                      # процесорів, рядків, стовпців тора
T = {'+': 1, '-': 1, '*': 2, '/': 4, 'neg': 1}


def hops(a, b):
    """Відстань між ПЕ a та b у торі 3x3."""
    (r1, c1), (r2, c2) = divmod(a, C), divmod(b, C)
    dr, dc = abs(r1 - r2), abs(c1 - c2)
    return min(dr, R - dr) + min(dc, C - dc)


def kids(o):
    return [c for c in (o.l, o.r) if c is not None and c.op is not None]


def get_ops(n, out):
    if n.op is not None:
        get_ops(n.l, out)
        if n.r:
            get_ops(n.r, out)
        out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('expr')
    ap.add_argument('--tc', type=int, default=1, help="час передачі між сусідніми ПЕ")
    ap.add_argument('--times', default="", help='напр. "+=1,*=2,/=4"')
    a = ap.parse_args()
    for kv in filter(None, a.times.split(',')):
        k, v = kv.split('=')
        T[k.strip()] = int(v)

    res = process(a.expr, quiet=True)
    if res['errors']:
        print("Вираз некоректний:", *res['errors'], sep="\n  - ")
        return
    ops = get_ops(res['root'], [])
    if not ops:
        return print("У виразі немає операцій.")

    # пріоритет = довжина критичного шляху до кореня
    parent = {c.id: o for o in ops for c in kids(o)}
    pr = {}
    def prio(o):
        if o.id not in pr:
            pr[o.id] = T[o.op] + (prio(parent[o.id]) if o.id in parent else 0)
        return pr[o.id]

    # розподіл: кожну операцію - на ПЕ, де вона завершиться найраніше
    free, fin, pe_of, sched = [0] * P, {}, {}, []
    for o in sorted(ops, key=lambda o: (-prio(o), o.id)):
        best = None
        for pe in range(P):
            ready = max([fin[c.id] + hops(pe_of[c.id], pe) * a.tc for c in kids(o)], default=0)
            start = max(free[pe], ready)
            if best is None or start + T[o.op] < best[0]:
                best = (start + T[o.op], start, pe)
        end, start, pe = best
        free[pe], fin[o.id], pe_of[o.id] = end, end, pe
        sched.append((start, end, pe, o))

    nm = lambda n: n.label if n.op is None else f"t{n.id}"
    print(f"Вираз: {a.expr}\nПаралельна форма: {res['form']}\n")
    for s, e, pe, o in sorted(sched, key=lambda x: (x[0], x[3].id)):
        f = f"-{nm(o.l)}" if o.op == 'neg' else f"{nm(o.l)} {o.op} {nm(o.r)}"
        print(f"[{s:>3}..{e:>3})  PE({pe // C},{pe % C})  t{o.id} = {f}")

    T1, Tp = sum(T[o.op] for o in ops), max(fin.values())
    S = T1 / Tp
    print(f"\nT1 = {T1}  Tp = {Tp}  S = {S:.2f}  E = S/P = {S / P:.2f}  (P={P}, тор {R}x{C}, tc={a.tc})")


if __name__ == '__main__':
    main()