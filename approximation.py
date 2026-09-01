from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math

import numerical
from models import ModelSpec


MIN_POINTS = 8
MAX_POINTS = 12


@dataclass(frozen=True)
class PointSet:
    x: tuple[float, ...]
    y: tuple[float, ...]

    @property
    def count(self) -> int:
        return len(self.x)


@dataclass(frozen=True)
class FitResult:
    model: ModelSpec
    coefficients: tuple[float, ...]
    values: tuple[float, ...]
    deviations: tuple[float, ...]
    sum_squares: float
    rms_deviation: float
    determination: float


@dataclass(frozen=True)
class FitFailure:
    model: ModelSpec
    reason: str
    issues: tuple[str, ...] = ()


def ensure_finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"Значение \"{name}\" выходит за допустимый диапазон.")


def parse_float_token(text: str, label: str) -> float:
    trimmed = "" if text is None else text.strip()
    if not trimmed:
        raise ValueError(f"Не заполнено поле \"{label}\".")
    normalized = trimmed.replace(",", ".")
    try:
        value = float(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Некорректное число в поле \"{label}\": {trimmed}. Используйте число с точкой или запятой."
        ) from exc
    ensure_finite(value, label)
    return value


def format_number(value: float) -> str:
    if not math.isfinite(value):
        return "-"
    if value == 0.0:
        return "0"
    return format(Decimal(str(value)).normalize(), "f")


def format_fixed(value: float, digits: int = 4) -> str:
    if not math.isfinite(value):
        return "-"
    if value != 0.0 and (abs(value) >= 1e6 or abs(value) < 1e-4):
        return f"{value:.{digits}e}"
    return f"{value:.{digits}f}"


def _validate(points: PointSet) -> None:
    if points.count < MIN_POINTS:
        raise ValueError(f"Нужно не меньше {MIN_POINTS} точек, введено {points.count}.")
    if points.count > MAX_POINTS:
        raise ValueError(f"Слишком много точек: {points.count}, допустимо не больше {MAX_POINTS}.")
    if len(set(points.x)) < 2:
        raise ValueError("Все значения x совпадают, приблизить такие данные нельзя.")


def determination_verdict(value: float) -> str:
    if not math.isfinite(value):
        return "достоверность оценить нельзя"
    if value >= 0.95:
        return "высокая точность аппроксимации"
    if value >= 0.75:
        return "удовлетворительная аппроксимация"
    if value >= 0.5:
        return "слабая аппроксимация"
    return "точность аппроксимации недостаточна"


def read_points(rows: list[tuple[int, str, str]]) -> PointSet:
    xs: list[float] = []
    ys: list[float] = []
    for number, x_text, y_text in rows:
        if not x_text.strip() and not y_text.strip():
            continue
        xs.append(parse_float_token(x_text, f"x в строке {number}"))
        ys.append(parse_float_token(y_text, f"y в строке {number}"))
    return PointSet(tuple(xs), tuple(ys))


def parse_rows(rows: list[tuple[int, str, str]]) -> PointSet:
    points = read_points(rows)
    _validate(points)
    return points


def split_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.replace(";", " ").replace("\t", " ").strip()
        if not line:
            continue
        tokens = line.split()
        if len(tokens) != 2:
            raise ValueError(f"Строка {number}: ожидаются два числа «x y», получено {len(tokens)}.")
        pairs.append((tokens[0], tokens[1]))
    if not pairs:
        raise ValueError("В файле нет ни одной точки. Добавьте точки в соответствии с заданным форматом.")
    return pairs


def fit_model(points: PointSet, model: ModelSpec) -> FitResult | FitFailure:
    if points.count < model.min_points:
        return FitFailure(model, f"нужно не меньше {model.min_points} точек")
    issues: list[str] = []
    if model.positive_x and min(points.x) <= 0.0:
        issues.append("для ln(x) нужно x > 0 во всех точках")
    if model.positive_y and min(points.y) <= 0.0:
        issues.append("для ln(y) нужно y > 0 во всех точках")
    if issues:
        return FitFailure(model, "линеаризация невозможна", tuple(issues))

    x = list(points.x)
    y = list(points.y)
    try:
        raw = model.fit(x, y)
    except (ValueError, ZeroDivisionError, OverflowError):
        return FitFailure(model, "не удалось решить систему")
    if raw is None:
        return FitFailure(model, "система уравнений вырождена")

    coefficients = tuple(float(value) for value in raw)
    if not all(math.isfinite(value) for value in coefficients):
        return FitFailure(model, "коэффициенты не определены")

    try:
        values = tuple(float(model.value(point, coefficients)) for point in points.x)
    except (ValueError, ZeroDivisionError, OverflowError):
        return FitFailure(model, "не определена в узлах таблицы")
    if not all(math.isfinite(value) for value in values):
        return FitFailure(model, "не определена в узлах таблицы")

    deviations = tuple(values[i] - y[i] for i in range(points.count))
    sum_squares = numerical.summa_kv_otkl(y, list(values))
    rms_deviation = numerical.srednekvadr_otkl(y, list(values))
    try:
        determination = numerical.determination_coef(y, list(values))
    except ZeroDivisionError:
        determination = math.nan
    return FitResult(model, coefficients, values, deviations, sum_squares, rms_deviation, determination)


def fit_models(points: PointSet, models: tuple[ModelSpec, ...]) -> list[FitResult | FitFailure]:
    if not models:
        raise ValueError("Не выбрана ни одна аппроксимирующая функция.")
    return [fit_model(points, model) for model in models]


def successful(results: list[FitResult | FitFailure]) -> list[FitResult]:
    return [item for item in results if isinstance(item, FitResult)]


def best_fit(results: list[FitResult | FitFailure]) -> FitResult | None:
    fitted = successful(results)
    if not fitted:
        return None
    return min(fitted, key=lambda item: item.rms_deviation)


def pearson_coefficient(points: PointSet) -> float:
    try:
        return numerical.pirson(list(points.x), list(points.y))
    except (ValueError, ZeroDivisionError):
        return math.nan
