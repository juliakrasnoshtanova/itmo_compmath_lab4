from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numerical
from datasets import sample_by_key

ASSETS = ROOT / "report_assets"
CURVE_LINEAR = "#b65436"
CURVE_QUADRATIC = "#26667f"
CURVE_EXACT = "#2e2923"


def render_computational_fit() -> None:
    sample = sample_by_key("variant4")
    x = list(sample.x)
    y = list(sample.y)

    a, b = numerical.linear(x, y)
    coefficients = numerical.polynom(x, y, 2)

    grid = [-4.0 + 4.0 * i / 400 for i in range(401)]
    exact = [15.0 * t / (t**4 + 4.0) for t in grid]
    linear = [numerical.linear_f(t, a, b) for t in grid]
    quadratic = [numerical.polynom_f(t, coefficients) for t in grid]

    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["font.size"] = 12
    figure, axes = plt.subplots(figsize=(8.0, 5.4), dpi=200)
    axes.plot(grid, exact, color=CURVE_EXACT, linewidth=1.8, label=r"$y = 15x/(x^4+4)$")
    axes.plot(grid, linear, color=CURVE_LINEAR, linewidth=1.8, label=r"$P_1(x) = ax + b$")
    axes.plot(grid, quadratic, color=CURVE_QUADRATIC, linewidth=1.8, label=r"$P_2(x) = a_0 + a_1x + a_2x^2$")
    axes.plot(x, y, "o", color=CURVE_EXACT, markersize=5, label="Табличные точки")

    axes.axhline(0.0, color="#8e8579", linewidth=0.9)
    axes.axvline(0.0, color="#8e8579", linewidth=0.9)
    axes.grid(True, color="#dcdcdc", linewidth=0.6)
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    axes.legend(loc="lower left", framealpha=1.0)
    figure.tight_layout()
    figure.savefig(ASSETS / "computational_fit.png")
    plt.close(figure)


def render_screenshots() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QStyleFactory

    from app import Lab4QtApp

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setFont(QFont("Helvetica Neue", 12))
    window = Lab4QtApp()
    window.resize(1400, 1040)
    window.show()
    page = window.page

    def settle() -> None:
        for _ in range(8):
            app.processEvents()

    def shoot(name: str) -> None:
        settle()
        page.sidebar.scroll.verticalScrollBar().setValue(0)
        page.right_scroll.verticalScrollBar().setValue(0)
        settle()
        window.grab().save(str(ASSETS / name))

    settle()
    page.solve()
    shoot("screenshot_variant4.png")

    page.sample_list.setCurrentRow(1)
    settle()
    page.solve()
    shoot("screenshot_lecture.png")

    page.sample_list.setCurrentRow(2)
    settle()
    page._fill_table([(str(1.0 + i), str(2.0 + 1.5 * i)) for i in range(5)])
    settle()
    page.solve()
    shoot("screenshot_invalid.png")

    page.sample_list.setCurrentRow(0)
    settle()
    for row in range(2, page.model_list.count()):
        page.model_list.item(row).setCheckState(Qt.CheckState.Unchecked)
    settle()
    page.solve()
    settle()
    page.plot.grab().save(str(ASSETS / "plot_variant4.png"))


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    render_computational_fit()
    render_screenshots()
    print("готово:", sorted(path.name for path in ASSETS.glob("*.png")))
