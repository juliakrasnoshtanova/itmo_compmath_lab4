import math
def linear(x, y):
    n = len(x)
    sx = sum(x)
    sxx = 0
    for i in x:
        sxx += i**2

    sy = sum(y)
    sxy = 0
    for i in range(n):
        sxy += x[i] * y[i]

    delta = sxx * n - sx * sx
    delta1 = sxy * n - sx * sy
    delta2 = sxx * sy - sx * sxy

    a = delta1 / delta
    b = delta2 / delta

    return a, b

def gauss(a, b):
    n = len(b)

    # расширенная матрица: к каждой строке A дописываем элемент b
    m = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(a[i][j])
        row.append(b[i])
        m.append(row)

    # прямой ход
    for k in range(n):
        # ищем главный элемент в k-м столбце
        glavnaya = k
        for i in range(k + 1, n):
            if abs(m[i][k]) > abs(m[glavnaya][k]):
                glavnaya = i

        if abs(m[glavnaya][k]) < 1e-12:
            return None  # матрица вырождена

        if glavnaya != k:
            tmp = m[k]
            m[k] = m[glavnaya]
            m[glavnaya] = tmp

        # обнуляем k-й столбец под диагональю
        for i in range(k + 1, n):
            c = m[i][k] / m[k][k]
            for j in range(k, n + 1):
                m[i][j] -= c * m[k][j]

    # обратный ход
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        summa = 0.0
        for j in range(i + 1, n):
            summa += m[i][j] * x[j]
        x[i] = (m[i][n] - summa) / m[i][i]

    return x

def polynom(x, y, p):
    n = len(x)
    b = []
    for k in range(p+1):
        sxy = 0
        for i in range(n):
            sxy += x[i]**k * y[i]
        b.append(sxy)

    a = []
    for k in range(p+1):
        sx = []
        for j in range(p+1):
            sx.append(0)
            for i in range(n):
                sx[j] += x[i] ** (k+j)
        a.append(sx)

    return gauss(a, b) #ответ на аппроксимацию

def vse_polozh(spisok):
    for i in spisok:
        if i <= 0:
            return False
    return True

def stepennaya(x, y):
    # ln x и ln y определены только при x > 0 и y > 0
    if not vse_polozh(x) or not vse_polozh(y):
        return None

    n = len(x)
    X = []
    Y = []
    for i in range(n):
        X.append(math.log(x[i]))
        Y.append(math.log(y[i]))
    A, B = linear(X, Y)
    a = math.exp(B)
    b = A
    return a, b

def exponen(x, y):
    # логарифмируем только y, поэтому нужно y > 0
    if not vse_polozh(y):
        return None

    n = len(x)
    X = []
    Y = []
    for i in range(n):
        X.append(x[i])
        Y.append(math.log(y[i]))
    A, B = linear(X, Y)
    a = math.exp(B)
    b = A
    return a, b

def logarifm(x, y):
    # заменяем только аргумент, поэтому нужно x > 0
    if not vse_polozh(x):
        return None

    n = len(x)
    X = []
    Y = []
    for i in range(n):
        X.append(math.log(x[i]))
        Y.append(y[i])
    A, B = linear(X, Y)
    a = A
    b = B
    return a, b

def linear_f(x, a, b):
    return x * a + b

def polynom_f(x, spisok_a):
    n = len(spisok_a)
    y = 0
    for i in range(n):
        y += spisok_a[i] * (x ** i)
    return y

def stepennaya_f(x, a, b):
    y = a * (x ** b)
    return y
def exponen_f(x, a, b):
    y = a * math.exp(b * x)
    return y

def logarifm_f(x, a, b):
    y = a * (math.log(x)) + b
    return y

def summa_kv_otkl(y_old, y_new):
    s = 0
    n = len(y_old)
    for i in range(n):
        s += (y_new[i] - y_old[i]) ** 2
    return s

def srednekvadr_otkl(y_old, y_new):
    n = len(y_old)
    b = math.sqrt(summa_kv_otkl(y_old, y_new) / n)
    return b

def determination_coef(y_old, y_new):
    n = len(y_old)
    niz = 0
    sr_sum_y_new = sum(y_new) / n
    for i in range(n):
        niz += (y_old[i] - sr_sum_y_new) ** 2
    r2 = 1 - summa_kv_otkl(y_old, y_new) / niz
    return r2

def pirson(x, y):
    n = len(x)
    x_cp = sum(x) / n
    y_cp = sum(y) / n
    verx = 0
    niz_x = 0
    niz_y = 0
    for i in range(n):
        verx += (x[i] - x_cp) * (y[i] - y_cp)
        niz_x += ((x[i] - x_cp)**2)
        niz_y += ((y[i] - y_cp)**2)
    niz = math.sqrt(niz_x * niz_y)
    r = verx/niz
    return r


if __name__ == "__main__":
    x = [-1, 2, -3, 0, -3.0000009845849594848999999]
    y = [-7, -15, 28, 1000, -9]
    a = polynom(x, y, 3)
    n = len(x)
    y_new = []
    for i in range(n):
        y_new.append(polynom_f(x[i], a))
    print(determination_coef(y, y_new), srednekvadr_otkl(y, y_new))
    print(a)
