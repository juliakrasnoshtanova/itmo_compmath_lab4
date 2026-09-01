from __future__ import annotations

from dataclasses import dataclass


CUSTOM_SAMPLE_KEY = "custom"


@dataclass(frozen=True)
class PointSample:
    key: str
    title: str
    note: str
    x: tuple[float, ...]
    y: tuple[float, ...]

    def as_text(self) -> str:
        return "\n".join(f"{x} {y}" for x, y in zip(self.x, self.y))


def _tabulate(numerator: float, shift: float, start: float, step: float, count: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    xs = []
    ys = []
    for i in range(count):
        x = round(start + step * i, 10)
        xs.append(x)
        ys.append(round(numerator * x / (x**4 + shift), 4))
    return tuple(xs), tuple(ys)


_VARIANT4_X, _VARIANT4_Y = _tabulate(15.0, 4.0, -4.0, 0.4, 11)


SAMPLES: tuple[PointSample, ...] = (
    PointSample(
        key="variant4",
        title="Вариант 4",
        note="y = 15x/(x^4+4), x ∈ [−4; 0], h = 0,4",
        x=_VARIANT4_X,
        y=_VARIANT4_Y,
    ),
    PointSample(
        key="lecture1",
        title="Пример (лекция 4, слайд 13)",
        note="8 точек, линейная зависимость",
        x=(1.2, 2.9, 4.1, 5.5, 6.7, 7.8, 9.2, 10.3),
        y=(7.4, 9.5, 11.1, 12.9, 14.6, 17.3, 18.2, 20.7),
    ),
)


def sample_by_key(key: str) -> PointSample:
    for sample in SAMPLES:
        if sample.key == key:
            return sample
    raise ValueError(f"Неизвестный набор точек: {key}.")
