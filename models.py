from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numerical


Coefficients = Sequence[float]
FitFn = Callable[[list[float], list[float]], Coefficients | None]
ValueFn = Callable[[float, Coefficients], float]


@dataclass(frozen=True)
class ModelSpec:
    key: str
    title: str
    formula: str
    parameters: tuple[str, ...]
    fit: FitFn
    value: ValueFn
    min_points: int
    positive_x: bool = False
    positive_y: bool = False


MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="linear",
        title="/•᷅‎‎•᷄\੭ Линейная",
        formula="f(x) = a*x + b",
        parameters=("a", "b"),
        fit=lambda x, y: numerical.linear(x, y),
        value=lambda x, c: numerical.linear_f(x, c[0], c[1]),
        min_points=2,
    ),
    ModelSpec(
        key="poly2",
        title="/•᷅‎‎•᷄\੭ Квадратичная",
        formula="f(x) = a0 + a1*x + a2*x^2",
        parameters=("a0", "a1", "a2"),
        fit=lambda x, y: numerical.polynom(x, y, 2),
        value=lambda x, c: numerical.polynom_f(x, list(c)),
        min_points=3,
    ),
    ModelSpec(
        key="poly3",
        title="/•᷅‎‎•᷄\੭ Кубическая",
        formula="f(x) = a0 + a1*x + a2*x^2 + a3*x^3",
        parameters=("a0", "a1", "a2", "a3"),
        fit=lambda x, y: numerical.polynom(x, y, 3),
        value=lambda x, c: numerical.polynom_f(x, list(c)),
        min_points=4,
    ),
    ModelSpec(
        key="power",
        title="/•᷅‎‎•᷄\੭ Степенная",
        formula="f(x) = a*x^b",
        parameters=("a", "b"),
        fit=lambda x, y: numerical.stepennaya(x, y),
        value=lambda x, c: numerical.stepennaya_f(x, c[0], c[1]),
        min_points=2,
        positive_x=True,
        positive_y=True,
    ),
    ModelSpec(
        key="exponential",
        title="/•᷅‎‎•᷄\੭ Экспоненциальная",
        formula="f(x) = a*e^(b*x)",
        parameters=("a", "b"),
        fit=lambda x, y: numerical.exponen(x, y),
        value=lambda x, c: numerical.exponen_f(x, c[0], c[1]),
        min_points=2,
        positive_y=True,
    ),
    ModelSpec(
        key="logarithmic",
        title="/•᷅‎‎•᷄\੭ Логарифмическая",
        formula="f(x) = a*ln(x) + b",
        parameters=("a", "b"),
        fit=lambda x, y: numerical.logarifm(x, y),
        value=lambda x, c: numerical.logarifm_f(x, c[0], c[1]),
        min_points=2,
        positive_x=True,
    ),
)


def model_by_key(key: str) -> ModelSpec:
    for model in MODELS:
        if model.key == key:
            return model
    raise ValueError(f"Неизвестная модель: {key}.")
