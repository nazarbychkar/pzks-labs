"""ЛР5, варіант 23: матрична (SIMD) система, 9 процесорів, тор (3x3): один тип операції на крок.
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


def route(a, b):
    """Найкоротший шлях по тору від ПЕ a до ПЕ b (список ПЕ): спочатку по стовпцях, потім по рядках."""
    (r, c), (r2, c2) = divmod(a, C), divmod(b, C)
    path = [a]
    while c != c2:
        c = (c + 1) % C if (c2 - c) % C <= C - (c2 - c) % C else (c - 1) % C
        path.append(r * C + c)
    while r != r2:
        r = (r + 1) % R if (r2 - r) % R <= R - (r2 - r) % R else (r - 1) % R
        path.append(r * C + c)
    return path


def kids(o):
    return [c for c in (o.l, o.r) if c is not None and c.op is not None]


def get_ops(n, out):
    if n.op is not None:
        get_ops(n.l, out)
        if n.r:
            get_ops(n.r, out)
        out.append(n)
    return out


def simulate_full(root, tc=1):
    """
    Матрична (SIMD) система: на кожному кроці всі зайняті ПЕ виконують ОДНУ операцію
    (один тип). Крок: обираємо тип операції за найвищим пріоритетом (критичний шлях)
    серед готових, запускаємо до P готових операцій цього типу на різних ПЕ.
    Результат з іншого ПЕ надходить через hops*tc. Повертає (розклад, T1, Tp, передачі).
    Передача = (старт, кінець, ПЕ-джерело, ПЕ-приймач, операція-джерело, операція-приймач).
    """
    ops = get_ops(root, [])
    if not ops:
        return [], 0, 0, []
    byid = {o.id: o for o in ops}
    parent = {c.id: o for o in ops for c in kids(o)}
    pr = {}
    def prio(o):                       # пріоритет = критичний шлях до кореня
        if o.id not in pr:
            pr[o.id] = T[o.op] + (prio(parent[o.id]) if o.id in parent else 0)
        return pr[o.id]

    fin, pe_of, sched, tr, left, t = {}, {}, [], [], set(byid), 0
    def ready(o, pe):                  # коли дані для o будуть на ПЕ pe
        return max([fin[c.id] + hops(pe_of[c.id], pe) * tc for c in kids(o)], default=0)

    while left:
        cand = [byid[i] for i in left if all(c.id in fin for c in kids(byid[i]))]
        go = [o for o in cand if min(ready(o, pe) for pe in range(P)) <= t]
        if not go:                     # чекаємо надходження даних по тору
            t = min(min(ready(o, pe) for pe in range(P)) for o in cand)
            continue
        typ = max(go, key=lambda o: (prio(o), -o.id)).op   # тип операції цього кроку
        free = list(range(P))
        for o in sorted((o for o in go if o.op == typ), key=lambda o: (-prio(o), o.id)):
            opts = [pe for pe in free if ready(o, pe) <= t]
            if not opts:
                continue
            pe = min(opts, key=lambda pe: (ready(o, pe), pe))
            free.remove(pe)
            for c in kids(o):          # передача результату, якщо він обчислений на іншому ПЕ
                if pe_of[c.id] != pe:
                    tr.append((fin[c.id], fin[c.id] + hops(pe_of[c.id], pe) * tc, pe_of[c.id], pe, c, o))
            fin[o.id], pe_of[o.id] = t + T[typ], pe
            sched.append((t, t + T[typ], pe, o))
            left.discard(o.id)
        t += T[typ]                    # наступний крок - після завершення всіх ПЕ
    return sched, sum(T[o.op] for o in ops), max(fin.values()), tr


def simulate(root, tc=1):
    sched, T1, Tp, _ = simulate_full(root, tc)
    return sched, T1, Tp


def print_schedule(sched, transfers=None):
    nm = lambda n: n.label if n.op is None else f"t{n.id}"
    print("Виконання операцій (на кожному кроці - один тип операції):")
    for s, e, pe, o in sorted(sched, key=lambda x: (x[0], x[3].id)):
        f = f"-{nm(o.l)}" if o.op == 'neg' else f"{nm(o.l)} {o.op} {nm(o.r)}"
        print(f"[{s:>3}..{e:>3})  PE({pe // C},{pe % C})  t{o.id} = {f}")
    if transfers is not None:
        print("\nПередачі по тору:")
        if not transfers:
            print("  (немає: всі залежності на одному ПЕ)")
        for s, e, a, b, c, o in sorted(transfers, key=lambda x: (x[0], x[4].id)):
            way = " -> ".join(f"PE({p // C},{p % C})" for p in route(a, b))
            print(f"[{s:>3}..{e:>3})  t{c.id}: {way}  ({hops(a, b)} кр.)  для t{o.id}")
        print(f"  Усього передач: {len(transfers)}, сумарно кроків: {sum(hops(t[2], t[3]) for t in transfers)}")


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
    sched, T1, Tp, tr = simulate_full(res['root'], a.tc)
    if not sched:
        return print("У виразі немає операцій.")
    print(f"Вираз: {a.expr}\nПаралельна форма: {res['form']}\n")
    print_schedule(sched, tr)
    S = T1 / Tp
    print(f"\nT1 = {T1}  Tp = {Tp}  S = {S:.2f}  E = S/P = {S / P:.2f}  (P={P}, тор {R}x{C}, tc={a.tc})")


if __name__ == '__main__':
    main()