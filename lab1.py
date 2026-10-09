import re

class SyntaxErrorItem:
    def __init__(self, pos: int, message: str, length: int = 1):
        self.pos = pos
        self.message = message
        self.length = length

class ExpressionAnalyzer:
    def __init__(self, expr: str):
        self.expr = expr
        self.errors = []
        
    def add_error(self, pos: int, message: str, length: int = 1):
        self.errors.append(SyntaxErrorItem(pos, message, length))

    def analyze(self):
        self.errors.clear()
        i = 0
        n = len(self.expr)
        
        state = 'EXPECT_OPERAND'  # EXPECT_OPERAND або EXPECT_OPERATOR
        paren_stack = []          # Стек для дужок: (символ, позиція)
        
        last_token = None
        last_token_pos = -1

        while i < n:
            # Пропуск пробілів та табуляцій
            if self.expr[i] in ' \t\r\n':
                i += 1
                continue

            ch = self.expr[i]

            # 1. Невідомі/неприпустимі символи
            if ch in '#$?@!&|':
                self.add_error(i, f"Невідомий символ або недозволений оператор '{ch}'")
                i += 1
                continue

            # 2. Некоректні числа з декількома крапками (наприклад, 2.01.2, 127.0.0.1)
            num_match = re.match(r'^\d+\.\d+(\.\d+)+', self.expr[i:])
            if num_match:
                err_str = num_match.group(0)
                self.add_error(i, f"Зайва десяткова крапка в дробовому числі '{err_str}'", len(err_str))
                i += len(err_str)
                state = 'EXPECT_OPERATOR'
                continue

            # 3. Некоректні ідентифікатори, що починаються з цифри (наприклад, 2v, 8t, 6x)
            bad_id_match = re.match(r'^\d+[a-zA-Z_][a-zA-Z0-9_]*', self.expr[i:])
            if bad_id_match:
                err_str = bad_id_match.group(0)
                self.add_error(i, f"Некоректний ідентифікатор '{err_str}' (не може починатися з цифри)", len(err_str))
                i += len(err_str)
                state = 'EXPECT_OPERATOR'
                continue

            # 4. Числа (Hex, Bin, Dec, Float)
            hex_match = re.match(r'^(0x[0-9a-fA-F]+|[0-9a-fA-F]+h)', self.expr[i:])
            bin_match = re.match(r'^(0b[01]+|[01]+b)', self.expr[i:])
            dec_match = re.match(r'^(\d+(\.\d*)?|\.\d+)', self.expr[i:])

            if hex_match or bin_match or dec_match:
                match = hex_match or bin_match or dec_match
                token_str = match.group(0)
                
                if state == 'EXPECT_OPERATOR':
                    self.add_error(i, f"Пропущено оператор перед константою '{token_str}'")
                
                i += len(token_str)
                state = 'EXPECT_OPERATOR'
                last_token = 'NUMBER'
                last_token_pos = i - len(token_str)
                continue

            # 5. Ідентифікатори (змінні / функції)
            id_match = re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*', self.expr[i:])
            if id_match:
                token_str = id_match.group(0)
                token_pos = i
                i += len(token_str)
                
                # Перевірка чи це функція (після назви йде '(')
                lookahead = i
                while lookahead < n and self.expr[lookahead] in ' \t':
                    lookahead += 1
                
                is_func = (lookahead < n and self.expr[lookahead] == '(')

                if state == 'EXPECT_OPERATOR':
                    self.add_error(token_pos, f"Пропущено оператор перед '{token_str}'")

                state = 'EXPECT_OPERAND' if is_func else 'EXPECT_OPERATOR'
                last_token = 'FUNC' if is_func else 'VAR'
                last_token_pos = token_pos
                continue

            # 6. Інкремент / Декремент (++ / --)
            if self.expr[i:i+2] in ['++', '--']:
                op = self.expr[i:i+2]
                if state == 'EXPECT_OPERATOR':
                    self.add_error(i, f"Неочікуваний оператор '{op}'")
                i += 2
                state = 'EXPECT_OPERAND'
                continue

            # 7. Подвійні оператори (**, //, /*)
            if self.expr[i:i+2] in ['**', '//', '/*']:
                op = self.expr[i:i+2]
                self.add_error(i, f"Неочікувана послідовність операторів '{op}'")
                i += 2
                state = 'EXPECT_OPERAND'
                continue

            # 8. Відкриваючі дужки: (, [, {
            if ch in '([{':
                if state == 'EXPECT_OPERATOR' and last_token not in ['FUNC']:
                    self.add_error(i, f"Пропущено оператор перед відкриваючою дужкою '{ch}'")
                
                paren_stack.append((ch, i))
                i += 1
                state = 'EXPECT_OPERAND'
                last_token = '('
                last_token_pos = i - 1
                continue

            # 9. Закриваючі дужки: ), ], }
            if ch in ')]}':
                if not paren_stack:
                    self.add_error(i, f"Зайва закриваюча дужка '{ch}' без відповідної відкриваючої")
                else:
                    open_ch, open_pos = paren_stack.pop()
                    expected = {')': '(', ']': '[', '}': '{'}[ch]
                    if open_ch != expected:
                        self.add_error(i, f"Невідповідність дужок: відкрита '{open_ch}', але закрита '{ch}'")
                    
                    if last_token == '(' and last_token_pos == open_pos:
                        self.add_error(i, "Порожні дужки не допускаються")

                if state == 'EXPECT_OPERAND' and last_token not in ['(', 'FUNC']:
                    self.add_error(i, f"Неочікувана закриваюча дужка '{ch}' після оператора")

                i += 1
                state = 'EXPECT_OPERATOR'
                last_token = ')'
                last_token_pos = i - 1
                continue

            # 10. Роздільник аргументів у функціях (кома)
            if ch == ',':
                if state == 'EXPECT_OPERAND':
                    self.add_error(i, "Неочікувана кома ',' (пропущено аргумент або оператор)")
                i += 1
                state = 'EXPECT_OPERAND'
                continue

            # 11. Арифметичні оператори: +, -, *, /, %, ^
            if ch in '+-*/%^':
                if state == 'EXPECT_OPERAND':
                    if ch in '+-':
                        i += 1
                        continue
                    else:
                        if i == 0:
                            self.add_error(i, f"Некоректний початок виразу з оператора '{ch}'")
                        else:
                            self.add_error(i, f"Неочікуваний оператор '{ch}'")
                else:
                    state = 'EXPECT_OPERAND'
                
                i += 1
                last_token = 'OP'
                last_token_pos = i - 1
                continue

            self.add_error(i, f"Неочікуваний символ '{ch}'")
            i += 1

        # Перевірка кінця виразу та незакритих дужок
        if state == 'EXPECT_OPERAND' and last_token not in [')', 'VAR', 'NUMBER']:
            self.add_error(n - 1 if n > 0 else 0, "Неочікуваний кінець виразу після оператора")

        while paren_stack:
            open_ch, open_pos = paren_stack.pop()
            self.add_error(open_pos, f"Відкриваюча дужка '{open_ch}' не має відповідної закриваючої")

        self.errors.sort(key=lambda x: x.pos)

    def print_report(self):
        print("[pos]")
        indices = "".join(str(i % 10) for i in range(len(self.expr)))
        print(indices)
        
        print("[expr]")
        print(self.expr)

        pointers = [' '] * len(self.expr)
        for err in self.errors:
            if 0 <= err.pos < len(self.expr):
                pointers[err.pos] = '^'
        
        print("[point]")
        print("".join(pointers))
        print("-" * len(self.expr))

        if not self.errors:
            print("Вираз успішно пройшов аналіз! Помилок не знайдено.")
        else:
            for err in self.errors:
                print(f"Позиція {err.pos:2d}: {err.message}")


if __name__ == "__main__":
    test_expressions = [
        "-a ++ b - 2v*func((t+2 -, sin(x/*2.01.2), )/8(-)**",
        "*a + nb -",
        "a ++ nb /* k -+/ g",
        "x + var1 + var_2 + var#4 + 6var_ + $7",
        "0.71/0.72.3 + .3 + 127.0.0.1*8. + 6.07ab",
        ")a+b( -(g+h)(g-k))*()) + (-b(t-2*x*(5)",
        "2(t) - f2(t) + g()/h(2, )*func(-t/q, f(4-t), (x+2)*(y-2))",
        "1239___++a_var(()++(#m_var) 21+3"
    ]

    for idx, test_expr in enumerate(test_expressions, 1):
        print(f"\n==================== ТЕСТ № {idx} ====================")
        analyzer = ExpressionAnalyzer(test_expr)
        analyzer.analyze()
        analyzer.print_report()