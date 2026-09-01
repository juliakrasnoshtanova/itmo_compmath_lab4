from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from approximation import FitResult, PointSet
from models import MODELS, ModelSpec


PLOT_BG = "#fbf8f2"
FRAME = "#ddd2c2"
GRID = "#eadfce"
AXIS = "#8e8579"
TEXT = "#2e2923"
POINT = "#2e2923"
POINT_HALO = "#fbf8f2"
CURVES = ("#b65436", "#26667f", "#1f6b43", "#a5822d", "#7a4b8c", "#a12828")

CURVE_SAMPLES = 720
MIN_SIDE = 560
EMPTY_SIDE = 5.0
LEGEND_ROW = 20


@dataclass(frozen=True)
class ViewBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


CURVE_BY_KEY = {model.key: CURVES[index % len(CURVES)] for index, model in enumerate(MODELS)}


def curve_color(model: ModelSpec) -> str:
    return CURVE_BY_KEY.get(model.key, CURVES[0])


class PlotWidget(QWidget):
    pointPicked = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(560)
        self.setMinimumHeight(560)
        self._message = "Задайте таблицу точек, чтобы увидеть облако данных."
        self._points: PointSet | None = None
        self._results: list[FitResult] = []
        self._view: ViewBox | None = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        side = max(self.width(), MIN_SIDE)
        if self.minimumHeight() != side:
            self.setMinimumHeight(side)
            self.setMaximumHeight(side)

    def show_message(self, message: str) -> None:
        self._message = message
        self._points = None
        self._results = []
        self.update()

    def reset_view(self) -> None:
        self._view = None

    def show_points(self, points: PointSet) -> None:
        self._apply(points, [])

    def show_fits(self, points: PointSet, results: list[FitResult]) -> None:
        self._apply(points, list(results))

    def _apply(self, points: PointSet, results: list[FitResult]) -> None:
        self._points = points
        self._results = results
        fitted = self._fit_view(points)
        if self._view is None or fitted is None:
            self._view = fitted
        else:
            self._view = ViewBox(
                min(self._view.x_min, fitted.x_min),
                max(self._view.x_max, fitted.x_max),
                min(self._view.y_min, fitted.y_min),
                max(self._view.y_max, fitted.y_max),
            )
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(PLOT_BG))

        outer = self.rect().adjusted(10, 10, -10, -10)
        painter.setPen(QPen(QColor(FRAME), 1))
        painter.drawRoundedRect(outer, 16, 16)

        if self._points is None:
            self._draw_message(painter, outer, self._message)
            return
        self._draw_chart(painter, outer)

    def _draw_message(self, painter: QPainter, rect: QRectF, message: str) -> None:
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("SF Pro Display", 15))
        painter.drawText(
            rect.adjusted(60, 40, -60, -40),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            message,
        )

    def _chart_rect(self) -> QRectF:
        return self.rect().adjusted(10, 10, -10, -10).adjusted(64, 28, -28, -56)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._points is None:
            return
        view = self._build_view()
        chart = self._chart_rect()
        if view is None or not chart.contains(event.position().toPoint()):
            return
        x = view.x_min + (event.position().x() - chart.left()) / chart.width() * (view.x_max - view.x_min)
        y = view.y_min + (chart.bottom() - event.position().y()) / chart.height() * (view.y_max - view.y_min)
        self.pointPicked.emit(x, y)

    def _draw_chart(self, painter: QPainter, outer: QRectF) -> None:
        assert self._points is not None
        view = self._build_view()
        if view is None:
            self._draw_message(painter, outer, "Не удалось построить область графика для этих данных.")
            return
        chart = self._chart_rect()

        self._draw_grid(painter, chart, view)
        self._draw_axes(painter, chart, view)
        for result in self._results:
            self._draw_curve(painter, chart, view, result, curve_color(result.model))
        self._draw_points(painter, chart, view)
        self._draw_legend(painter, chart, view)

    def _build_view(self) -> ViewBox | None:
        return self._view

    @staticmethod
    def _fit_view(points: PointSet) -> ViewBox | None:
        if not points.x:
            return ViewBox(-EMPTY_SIDE, EMPTY_SIDE, -EMPTY_SIDE, EMPTY_SIDE)
        x_low = min(points.x)
        x_high = max(points.x)
        x_padding = max((x_high - x_low) * 0.12, 0.5)

        y_low = min(points.y)
        y_high = max(points.y)
        y_span = (y_high - y_low) or max(abs(y_high), 1.0)
        y_padding = y_span * 0.12

        view = ViewBox(x_low - x_padding, x_high + x_padding, y_low - y_padding, y_high + y_padding)
        if view.x_max <= view.x_min or view.y_max <= view.y_min:
            return None
        return view

    @staticmethod
    def _sample_grid(x_min: float, x_max: float) -> list[float]:
        return [x_min + (x_max - x_min) * i / CURVE_SAMPLES for i in range(CURVE_SAMPLES + 1)]

    @staticmethod
    def _safe_value(result: FitResult, x: float) -> float:
        try:
            value = float(result.model.value(x, result.coefficients))
        except Exception:
            return math.nan
        return value if math.isfinite(value) else math.nan

    def _draw_grid(self, painter: QPainter, rect: QRectF, view: ViewBox) -> None:
        painter.save()
        painter.setPen(QPen(QColor(GRID), 1))
        for i in range(9):
            x = rect.left() + rect.width() * i / 8
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for i in range(7):
            y = rect.top() + rect.height() * i / 6
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("Menlo", 10))
        for i in range(9):
            value = view.x_min + (view.x_max - view.x_min) * i / 8
            x = rect.left() + rect.width() * i / 8
            painter.drawText(QRectF(x - 40, rect.bottom() + 10, 80, 18), Qt.AlignmentFlag.AlignHCenter, self._short(value))
        for i in range(7):
            value = view.y_max - (view.y_max - view.y_min) * i / 6
            y = rect.top() + rect.height() * i / 6
            painter.drawText(QRectF(rect.left() - 60, y - 10, 52, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._short(value))
        painter.restore()

    def _draw_axes(self, painter: QPainter, rect: QRectF, view: ViewBox) -> None:
        painter.save()
        painter.setPen(QPen(QColor(AXIS), 2))
        if view.x_min <= 0.0 <= view.x_max:
            x0 = self._to_canvas_x(rect, view, 0.0)
            painter.drawLine(QPointF(x0, rect.top()), QPointF(x0, rect.bottom()))
        if view.y_min <= 0.0 <= view.y_max:
            y0 = self._to_canvas_y(rect, view, 0.0)
            painter.drawLine(QPointF(rect.left(), y0), QPointF(rect.right(), y0))
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("SF Pro Display", 12, QFont.Weight.Medium))
        painter.drawText(QRectF(rect.center().x() - 30, rect.bottom() + 28, 60, 18), Qt.AlignmentFlag.AlignCenter, "x")
        painter.drawText(QRectF(rect.left(), rect.top() - 24, 60, 18), Qt.AlignmentFlag.AlignLeft, "y")
        painter.restore()

    def _draw_curve(self, painter: QPainter, rect: QRectF, view: ViewBox, result: FitResult, color: str) -> None:
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(color), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        span = view.y_max - view.y_min
        lower = view.y_min - span
        upper = view.y_max + span
        current: list[QPointF] = []
        previous_y: float | None = None
        for x in self._sample_grid(view.x_min, view.x_max):
            y = self._safe_value(result, x)
            valid = math.isfinite(y) and lower <= y <= upper
            if valid and previous_y is not None and abs(y - previous_y) > span * 0.45:
                valid = False
            if not valid:
                self._flush_path(painter, current)
                current = []
                previous_y = None
                continue
            current.append(QPointF(self._to_canvas_x(rect, view, x), self._to_canvas_y(rect, view, y)))
            previous_y = y
        self._flush_path(painter, current)
        painter.restore()

    def _draw_points(self, painter: QPainter, rect: QRectF, view: ViewBox) -> None:
        assert self._points is not None
        painter.save()
        for x, y in zip(self._points.x, self._points.y):
            center = QPointF(self._to_canvas_x(rect, view, x), self._to_canvas_y(rect, view, y))
            painter.setPen(QPen(QColor(POINT_HALO), 3))
            painter.setBrush(QColor(POINT_HALO))
            painter.drawEllipse(center, 5.6, 5.6)
            painter.setPen(QPen(QColor(POINT), 1))
            painter.setBrush(QColor(POINT))
            painter.drawEllipse(center, 3.8, 3.8)
        painter.restore()

    def _draw_legend(self, painter: QPainter, rect: QRectF, view: ViewBox) -> None:
        if not self._results:
            return
        painter.save()
        painter.setFont(QFont("SF Pro Display", 11))
        metrics = painter.fontMetrics()
        width = 0
        for result in self._results:
            width = max(width, metrics.horizontalAdvance(result.model.title))
        box = self._legend_box(rect, view, width + 52, LEGEND_ROW * len(self._results) + 16)

        background = QColor(PLOT_BG)
        background.setAlpha(240)
        painter.setPen(QPen(QColor(FRAME), 1))
        painter.setBrush(background)
        painter.drawRoundedRect(box, 8, 8)

        for index, result in enumerate(self._results):
            y = box.top() + 8 + LEGEND_ROW * index + LEGEND_ROW / 2
            painter.setPen(QPen(QColor(curve_color(result.model)), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(box.left() + 10, y), QPointF(box.left() + 32, y))
            painter.setPen(QColor(TEXT))
            painter.drawText(
                QRectF(box.left() + 40, y - LEGEND_ROW / 2, width + 8, LEGEND_ROW),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                result.model.title,
            )
        painter.restore()

    def _legend_box(self, rect: QRectF, view: ViewBox, box_width: float, box_height: float) -> QRectF:
        assert self._points is not None
        corners = (
            QRectF(rect.right() - box_width - 10, rect.top() + 10, box_width, box_height),
            QRectF(rect.left() + 10, rect.top() + 10, box_width, box_height),
            QRectF(rect.right() - box_width - 10, rect.bottom() - box_height - 10, box_width, box_height),
            QRectF(rect.left() + 10, rect.bottom() - box_height - 10, box_width, box_height),
        )
        centers = [
            QPointF(self._to_canvas_x(rect, view, x), self._to_canvas_y(rect, view, y))
            for x, y in zip(self._points.x, self._points.y)
        ]
        best = corners[0]
        best_hits = None
        for corner in corners:
            zone = corner.adjusted(-8, -8, 8, 8)
            hits = sum(1 for point in centers if zone.contains(point))
            if best_hits is None or hits < best_hits:
                best = corner
                best_hits = hits
            if best_hits == 0:
                break
        return best

    def _flush_path(self, painter: QPainter, points: list[QPointF]) -> None:
        if len(points) < 2:
            return
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter.drawPath(path)

    def _to_canvas_x(self, rect: QRectF, view: ViewBox, x: float) -> float:
        return rect.left() + (x - view.x_min) / (view.x_max - view.x_min) * rect.width()

    def _to_canvas_y(self, rect: QRectF, view: ViewBox, y: float) -> float:
        return rect.bottom() - (y - view.y_min) / (view.y_max - view.y_min) * rect.height()

    def _short(self, value: float) -> str:
        if abs(value) >= 1000 or (0 < abs(value) < 0.001):
            return f"{value:.2e}"
        return f"{value:.4g}"
