from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from approximation import (
    MAX_POINTS,
    MIN_POINTS,
    FitFailure,
    FitResult,
    PointSet,
    best_fit,
    determination_verdict,
    fit_models,
    format_fixed,
    format_number,
    parse_rows,
    pearson_coefficient,
    read_points,
    split_pairs,
    successful,
)
from datasets import CUSTOM_SAMPLE_KEY, SAMPLES, sample_by_key
from models import MODELS
from plotting import PlotWidget, curve_color


APP_BG = "#f4efe4"
CARD_BG = "#fffaf0"
BORDER = "#d9cdbd"
TEXT = "#2e2923"
MUTED = "#665c52"
ACCENT = "#a5552d"
ACCENT_DARK = "#844220"
SUCCESS = "#1f6b43"
ERROR = "#a12828"
REQUIRED = "#a5442c"
OPTIONAL = "#2f7a52"


def _set_app_font(widget: QWidget, size: int, weight: int = QFont.Weight.Normal) -> None:
    font = QFont("SF Pro Display", size, weight)
    if font.family() == ".AppleSystemUIFont":
        font = QFont()
        font.setPointSize(size)
        font.setWeight(weight)
    widget.setFont(font)


class Card(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        _set_app_font(title_label, 13, QFont.Weight.DemiBold)
        layout.addWidget(title_label)


class Sidebar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SidebarHost")
        self.scroll = QScrollArea()
        self.scroll.setObjectName("SidebarScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def add_card(self, title: str) -> Card:
        card = Card(title)
        self.content_layout.insertWidget(self.content_layout.count() - 1, card)
        return card


class Lab4Page(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.file_report: str | None = None
        self._custom_pairs: list[tuple[str, str]] = []
        self._last_points: PointSet | None = None
        self._last_results: list[FitResult | FitFailure] | None = None
        self._check_changed = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self._build()
        self._populate()
        self.refresh_preview()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)
        layout.addWidget(splitter)

        self.sidebar = Sidebar()
        self.sidebar.setMinimumWidth(390)
        self.sidebar.setMaximumWidth(460)
        splitter.addWidget(self.sidebar)

        self.plot = PlotWidget()
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        right = QWidget()
        right.setObjectName("RightHost")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.plot, 0)

        deviations_card = Card("Отклонения наилучшей модели")
        self.deviations_hint = QLabel("Нажмите «Вычислить», чтобы построить таблицу отклонений.")
        self.deviations_hint.setObjectName("HintLabel")
        self.deviations_hint.setWordWrap(True)
        deviations_card.layout().addWidget(self.deviations_hint)

        self.deviations_table = QTableWidget(0, 4)
        self.deviations_table.setHorizontalHeaderLabels(["x", "y", "φ(x)", "ε"])
        self.deviations_table.setFont(QFont("Menlo", 11))
        self.deviations_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.deviations_table.horizontalHeader().setHighlightSections(False)
        self.deviations_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.deviations_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.deviations_table.verticalHeader().setDefaultSectionSize(25)
        self.deviations_table.verticalHeader().setHighlightSections(False)
        self.deviations_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.deviations_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        deviations_card.layout().addWidget(self.deviations_table)
        right_layout.addWidget(deviations_card, 0)
        right_layout.addStretch(1)

        self.right_scroll = QScrollArea()
        self.right_scroll.setObjectName("RightScroll")
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.right_scroll.setWidget(right)
        self.plot.pointPicked.connect(self.add_picked_point)

        splitter.addWidget(self.right_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        data_card = self.sidebar.add_card("⋆ ˚｡⋆୨ Исходные данные ୧⋆ ˚｡⋆")
        data_layout = data_card.layout()

        sample_label = QLabel("Набор точек ૮ ˶ᵔ ᵕ ᵔ˶ ა ⋆ˊˎ-")
        sample_label.setObjectName("HintLabel")
        data_layout.addWidget(sample_label)
        self.sample_list = QListWidget()
        self._configure_selector_list(self.sample_list)
        self.sample_list.currentRowChanged.connect(self._on_sample_changed)
        data_layout.addWidget(self.sample_list)

        points_label = QLabel("˚₊‧꒰აТаблица точек໒꒱‧₊˚ вводите вручную или кликайте по графику")
        points_label.setObjectName("HintLabel")
        points_label.setWordWrap(True)
        data_layout.addWidget(points_label)

        self.points_table = QTableWidget(MAX_POINTS, 2)
        self.points_table.setHorizontalHeaderLabels(["x", "y"])
        self.points_table.setFont(QFont("Menlo", 11))
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.points_table.horizontalHeader().setHighlightSections(False)
        self.points_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.points_table.verticalHeader().setDefaultSectionSize(25)
        self.points_table.verticalHeader().setHighlightSections(False)
        for column, title in enumerate(("x", "y")):
            header_item = QTableWidgetItem(title)
            header_item.setForeground(QColor(MUTED))
            self.points_table.setHorizontalHeaderItem(column, header_item)
        for row in range(MAX_POINTS):
            number = QTableWidgetItem(str(row + 1))
            number.setForeground(QColor(REQUIRED if row < MIN_POINTS else OPTIONAL))
            self.points_table.setVerticalHeaderItem(row, number)
        self.points_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.points_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.points_table.itemChanged.connect(self._on_points_changed)
        data_layout.addWidget(self.points_table)

        self.rows_legend = QLabel(
            f"<span style='color:{REQUIRED}'>ʚଓ кол-во точек: 1 - {MIN_POINTS} -- обязательно</span><br>"
            f"<span style='color:{OPTIONAL}'>ʚଓ {MIN_POINTS + 1} - {MAX_POINTS} -- по необходимости</span>"
        )
        self.rows_legend.setObjectName("HintLabel")
        self.rows_legend.setWordWrap(True)
        data_layout.addWidget(self.rows_legend)

        self.load_button = QPushButton("𓂃 Загрузить точки из файла 𓂃")
        self.load_button.clicked.connect(self.load_points)
        data_layout.addWidget(self.load_button)

        self.file_format_label = QLabel("♡ Формат файла: каждая точка с новой строки, x и y через пробел или ;")
        self.file_format_label.setObjectName("HintLabel")
        self.file_format_label.setWordWrap(True)
        data_layout.addWidget(self.file_format_label)

        self.reset_button = QPushButton("୨୧ Сбросить точки ୨୧ ")
        self.reset_button.clicked.connect(self.reset_points)
        data_layout.addWidget(self.reset_button)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setWordWrap(True)
        data_layout.addWidget(self.hint_label)

        models_card = self.sidebar.add_card("✿ Аппроксимирующие функции ✿")
        models_layout = models_card.layout()
        models_hint = QLabel("Считаются все. Отметьте, какие показывать на графике")
        models_hint.setObjectName("HintLabel")
        models_hint.setWordWrap(True)
        models_layout.addWidget(models_hint)
        self.model_list = QListWidget()
        self._configure_selector_list(self.model_list)
        self.model_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        models_layout.addWidget(self.model_list)

        actions_card = self.sidebar.add_card("𖥸 Действия 𖥸")
        actions_layout = actions_card.layout()
        self.solve_button = QPushButton("⟡ Вычислить ⟡")
        self.solve_button.setObjectName("PrimaryButton")
        self.solve_button.clicked.connect(self.solve)
        actions_layout.addWidget(self.solve_button)

        self.save_button = QPushButton("𝜗𝜚 Сохранить результат 𝜗𝜚")
        self.save_button.clicked.connect(self.save)
        actions_layout.addWidget(self.save_button)

        self.status_label = QLabel("Готово к работе.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        actions_layout.addWidget(self.status_label)

        result_card = self.sidebar.add_card("｡⭒⑅Результат⑅⭒｡")
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setMinimumHeight(340)
        _set_app_font(self.result_box, 11)
        self.result_box.setHtml(self._placeholder_html())
        result_card.layout().addWidget(self.result_box)

    def _populate(self) -> None:
        for sample in SAMPLES:
            item = QListWidgetItem(f"{sample.title}\n{sample.note}")
            item.setData(Qt.ItemDataRole.UserRole, sample.key)
            item.setSizeHint(QSize(0, 60))
            self.sample_list.addItem(item)
        custom_item = QListWidgetItem("Свои точки")
        custom_item.setData(Qt.ItemDataRole.UserRole, CUSTOM_SAMPLE_KEY)
        custom_item.setSizeHint(QSize(0, 44))
        self.sample_list.addItem(custom_item)

        for model in MODELS:
            item = QListWidgetItem(f"{model.title}\n{model.formula}")
            item.setData(Qt.ItemDataRole.UserRole, model.key)
            item.setSizeHint(QSize(0, 60))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.model_list.addItem(item)

        self._lock_selector_height(self.sample_list, self.sample_list.count())
        self._lock_selector_height(self.model_list, self.model_list.count())
        self.sample_list.setCurrentRow(0)
        self._update_reset_state()
        self.model_list.itemChanged.connect(self._on_model_item_changed)
        self.model_list.itemClicked.connect(self._on_model_item_clicked)

    def _checked_keys(self) -> set:
        keys = set()
        for row in range(self.model_list.count()):
            item = self.model_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                keys.add(str(item.data(Qt.ItemDataRole.UserRole)))
        return keys

    def _refresh_curves(self) -> None:
        if self._last_points is None or self._last_results is None:
            return
        keys = self._checked_keys()
        shown = [item for item in successful(self._last_results) if item.model.key in keys]
        self.plot.show_fits(self._last_points, shown)

    def _on_model_item_changed(self, _item: QListWidgetItem) -> None:
        self._check_changed = True
        self._refresh_curves()

    def _on_model_item_clicked(self, item: QListWidgetItem) -> None:
        if not self._check_changed:
            state = Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
            item.setCheckState(state)
        self._check_changed = False

    def _is_custom_sample_selected(self) -> bool:
        item = self.sample_list.currentItem()
        return item is not None and item.data(Qt.ItemDataRole.UserRole) == CUSTOM_SAMPLE_KEY

    def _on_sample_changed(self, row: int) -> None:
        if row < 0:
            return
        with self._frozen():
            self._switch_sample()

    def _switch_sample(self) -> None:
        if self._is_custom_sample_selected():
            self._update_reset_state()
            if any(x.strip() or y.strip() for x, y in self._custom_pairs):
                self._fill_table(self._custom_pairs)
            else:
                self.reset_points()
            return
        self._update_reset_state()
        item = self.sample_list.currentItem()
        sample = sample_by_key(str(item.data(Qt.ItemDataRole.UserRole)))
        self._fill_table([(str(x), str(y)) for x, y in zip(sample.x, sample.y)])

    def _on_points_changed(self, _item: QTableWidgetItem | None = None) -> None:
        self._select_custom_sample()
        self._remember_custom()
        self._update_hint()
        self.preview_timer.start()

    def _update_deviations(self, points: PointSet | None, best: FitResult | None) -> None:
        table = self.deviations_table
        table.clearContents()
        if points is None or best is None:
            table.setRowCount(0)
            self.deviations_hint.setText("Нажмите «Вычислить», чтобы построить таблицу отклонений.")
        else:
            self.deviations_hint.setText(f"{best.model.title}:   {self._model_equation(best)}")
            table.setRowCount(points.count)
            for row in range(points.count):
                values = (points.x[row], points.y[row], best.values[row], best.deviations[row])
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(format_number(value))
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row, column, cell)
        height = (
            table.horizontalHeader().sizeHint().height()
            + 25 * table.rowCount()
            + 2 * table.frameWidth()
        )
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    def adjust_metrics(self) -> None:
        text = self.hint_label.text()
        self.hint_label.setText("A\nA")
        self.hint_label.setFixedHeight(self.hint_label.sizeHint().height())
        self.hint_label.setText(text)
        height = (
            self.points_table.horizontalHeader().sizeHint().height()
            + sum(self.points_table.rowHeight(row) for row in range(MAX_POINTS))
            + 2 * self.points_table.frameWidth()
        )
        self.points_table.setMinimumHeight(height)
        self.points_table.setMaximumHeight(height)

    def _table_rows(self) -> list[tuple[int, str, str]]:
        rows = []
        for row in range(self.points_table.rowCount()):
            x_item = self.points_table.item(row, 0)
            y_item = self.points_table.item(row, 1)
            rows.append((row + 1, "" if x_item is None else x_item.text(), "" if y_item is None else y_item.text()))
        return rows

    def _current_points(self) -> PointSet:
        return parse_rows(self._table_rows())

    def _remember_custom(self) -> None:
        if self._is_custom_sample_selected():
            self._custom_pairs = [(x, y) for _, x, y in self._table_rows()]

    def _fill_table(self, pairs: list[tuple[str, str]]) -> None:
        with self._frozen():
            self.plot.reset_view()
            self.file_report = None
            self._last_points = None
            self._last_results = None
            self.result_box.setHtml(self._placeholder_html())
            self._update_deviations(None, None)
            self.points_table.blockSignals(True)
            self.points_table.clearContents()
            for row in range(MAX_POINTS):
                x_text, y_text = pairs[row] if row < len(pairs) else ("", "")
                self.points_table.setItem(row, 0, QTableWidgetItem(x_text))
                self.points_table.setItem(row, 1, QTableWidgetItem(y_text))
            self.points_table.blockSignals(False)
            self._update_hint()
            self.refresh_preview()


    def _select_custom_sample(self) -> None:
        if self._is_custom_sample_selected():
            return
        self.sample_list.blockSignals(True)
        self.sample_list.setCurrentRow(self.sample_list.count() - 1)
        self.sample_list.blockSignals(False)
        self._update_reset_state()

    def _update_reset_state(self) -> None:
        self.reset_button.setEnabled(self._is_custom_sample_selected())

    @contextmanager
    def _frozen(self):
        if not self.updatesEnabled():
            yield
            return
        sidebar = self.sidebar.scroll.verticalScrollBar()
        right = self.right_scroll.verticalScrollBar()
        offsets = (sidebar.value(), right.value())
        self.setUpdatesEnabled(False)
        try:
            yield
        finally:
            sidebar.setValue(offsets[0])
            right.setValue(offsets[1])
            self.setUpdatesEnabled(True)

    def reset_points(self) -> None:
        self._custom_pairs = []
        self._fill_table([])
        self._set_status("︵ 𐔌 Таблица очищена ꪆ⏜ׅ ✶ вводите точки вручную или кликайте по графику.", success=True)

    def _update_hint(self) -> None:
        try:
            points = self._current_points()
        except ValueError as exc:
            self.hint_label.setText(str(exc))
            return
        self.hint_label.setText(
            f"Точек: {points.count}\n"
            f"x ∈ [{format_fixed(min(points.x), 3)}; {format_fixed(max(points.x), 3)}]   "
            f"y ∈ [{format_fixed(min(points.y), 3)}; {format_fixed(max(points.y), 3)}]"
        )


    def refresh_preview(self) -> None:
        try:
            points = read_points(self._table_rows())
        except ValueError as exc:
            self.plot.show_message(str(exc))
            return
        self.plot.show_points(points)

    def add_picked_point(self, x: float, y: float) -> None:
        row = self._first_free_row()
        if row is None:
            self._set_status(f"Таблица заполнена: {MAX_POINTS} из {MAX_POINTS} точек.", success=False)
            return
        self.points_table.blockSignals(True)
        self.points_table.item(row, 0).setText(f"{x:.3f}")
        self.points_table.item(row, 1).setText(f"{y:.3f}")
        self.points_table.blockSignals(False)
        self.points_table.setCurrentCell(row, 0)
        self._select_custom_sample()
        self._remember_custom()
        self._update_hint()
        self.refresh_preview()
        self._set_status(f"Точка ({x:.3f}; {y:.3f}) добавлена в строку {row + 1}.", success=True)

    def _first_free_row(self) -> int | None:
        for row in range(MAX_POINTS):
            x_item = self.points_table.item(row, 0)
            y_item = self.points_table.item(row, 1)
            x_text = "" if x_item is None else x_item.text().strip()
            y_text = "" if y_item is None else y_item.text().strip()
            if not x_text and not y_text:
                return row
        return None

    def solve(self) -> None:
        try:
            points = self._current_points()
            results = fit_models(points, MODELS)
            fitted = successful(results)
            self._last_points = points
            self._last_results = results
            self.result_box.setHtml(self._format_report(points, results))
            best = best_fit(results)
            report = self.result_box.toPlainText().strip()
            self.file_report = report if best is None else report + "\n" + self._deviations_text(points, best)
            self._refresh_curves()
            self._update_deviations(points, best)
            if not fitted:
                self._set_status("Ни одна модель не применима к этим данным.", success=False)
            else:
                self._set_status(f"Наилучшая модель: {best.model.title}.", success=True)
        except Exception as exc:
            self.file_report = None
            self._last_points = None
            self._last_results = None
            self._update_deviations(None, None)
            self.result_box.setHtml(f"<div style='color:{ERROR}'>{exc}</div>")
            self._set_status(str(exc), success=False)

    def load_points(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузка таблицы точек",
            str(Path.cwd()),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        try:
            pairs = split_pairs(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            self._set_status(f"Не удалось прочитать файл: {exc}", success=False)
            return
        except ValueError as exc:
            self._set_status(str(exc), success=False)
            return
        if len(pairs) > MAX_POINTS:
            self._set_status(f"В файле {len(pairs)} точек, допустимо не больше {MAX_POINTS}.", success=False)
            return
        self._select_custom_sample()
        self._fill_table(pairs)
        self._remember_custom()
        self._set_status(f"Точки загружены из файла «{Path(path).name}».", success=True)

    def save(self) -> None:
        if self.file_report is None:
            QMessageBox.information(self, "Нет данных", "Сначала получите решение, потом его можно сохранить.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранение результата",
            str(Path(__file__).resolve().parent / "result.txt"),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        Path(path).write_text(self.file_report.strip() + "\n", encoding="utf-8")
        self._set_status(f"Результат сохранен в файл «{Path(path).name}».", success=True)

    @staticmethod
    def _placeholder_html() -> str:
        return f"<div style='color:{MUTED}'>Нажмите «Вычислить», чтобы подобрать аппроксимирующие функции.</div>"

    @staticmethod
    def _card_html(content: str, background: str) -> str:
        return (
            f"<table width='100%' cellpadding='7' cellspacing='0' "
            f"style='background-color:{background}; border:1px solid {BORDER}'>"
            f"<tr><td>{content}</td></tr></table>"
            f"<div style='font-size:3pt'>&nbsp;</div>"
        )

    @staticmethod
    def _verdict_color(value: float) -> str:
        if value >= 0.95:
            return SUCCESS
        if value >= 0.75:
            return "#a5822d"
        if value >= 0.5:
            return ACCENT
        return ERROR

    @staticmethod
    def _value_html(label: str, text: str) -> str:
        return f"<br><span style='color:{MUTED}'>{label}</span> = <span style='color:{TEXT}'>{text}</span>"

    def _model_card_html(self, item: FitResult | FitFailure) -> str:
        if isinstance(item, FitFailure):
            content = (
                f"<span style='color:{MUTED}; font-weight:bold'>{item.model.title}</span>"
                f"<br><span style='color:{MUTED}'>{item.model.formula}</span>"
                f"<br><span style='color:{ERROR}'>не построена: {item.reason}</span>"
            )
            for issue in item.issues:
                content += f"<br><span style='color:{MUTED}'>{issue}</span>"
            return self._card_html(content, "#f7f2ea")

        content = (
            f"<span style='color:{curve_color(item.model)}; font-weight:bold'>{item.model.title}</span>"
            f"<br><span style='color:{MUTED}'>{item.model.formula}</span>"
        )
        for name, value in zip(item.model.parameters, item.coefficients):
            content += self._value_html(name, format_number(value))
        content += self._value_html("S", format_number(item.sum_squares))
        content += self._value_html("d", format_number(item.rms_deviation))
        content += self._value_html("R²", format_number(item.determination))
        content += (
            f"<br><span style='color:{self._verdict_color(item.determination)}'>"
            f"{determination_verdict(item.determination)}</span>"
        )
        return self._card_html(content, CARD_BG)

    def _ranking_html(self, fitted: list[FitResult]) -> str:
        content = f"<span style='color:{MUTED}; font-weight:bold'>Сравнение по отклонению d</span>"
        for place, item in enumerate(sorted(fitted, key=lambda value: value.rms_deviation), start=1):
            weight = "bold" if place == 1 else "normal"
            content += (
                f"<br><span style='color:{MUTED}'>{place}.</span> "
                f"<span style='color:{curve_color(item.model)}; font-weight:{weight}'>{item.model.title}</span>"
                f"<span style='color:{MUTED}'> — </span>"
                f"<span style='font-weight:{weight}'>{format_number(item.rms_deviation)}</span>"
            )
        return self._card_html(content, CARD_BG)

    def _best_card_html(self, best: FitResult) -> str:
        content = (
            f"<span style='color:{ACCENT_DARK}; font-weight:bold'>Наилучшая модель</span>"
            f"<br><span style='color:{curve_color(best.model)}; font-weight:bold'>{best.model.title}</span>"
            f"<br><span style='color:{MUTED}'>{best.model.formula}</span>"
        )
        for name, value in zip(best.model.parameters, best.coefficients):
            content += self._value_html(name, format_number(value))
        content += self._value_html("d", format_number(best.rms_deviation))
        return self._card_html(content, "#f4e5d9")

    def _format_report(self, points: PointSet, results: list[FitResult | FitFailure]) -> str:
        parts = [
            f"<div style='color:{MUTED}'>Число точек n: "
            f"<span style='color:{TEXT}; font-weight:bold'>{points.count}</span>"
            f"<br>Коэф. корреляции Пирсона r = "
            f"<span style='color:{TEXT}; font-weight:bold'>{format_number(pearson_coefficient(points))}</span>"
            f"<br>Построено моделей: "
            f"<span style='color:{TEXT}; font-weight:bold'>{len(successful(results))} из {len(results)}</span>"
            f"</div><div style='font-size:5pt'>&nbsp;</div>"
        ]
        for item in results:
            parts.append(self._model_card_html(item))

        fitted = successful(results)
        if not fitted:
            parts.append(f"<div style='color:{ERROR}'>Ни одна модель не применима к этим данным.</div>")
            return "".join(parts)

        parts.append(self._ranking_html(fitted))
        parts.append(self._best_card_html(best_fit(results)))
        return "".join(parts)

    def _deviations_text(self, points: PointSet, best: FitResult) -> str:
        rows = [("x", "y", "f(x)", "e")]
        for i in range(points.count):
            rows.append((
                format_number(points.x[i]),
                format_number(points.y[i]),
                format_number(best.values[i]),
                format_number(best.deviations[i]),
            ))
        widths = [max(len(row[column]) for row in rows) + 2 for column in range(4)]
        lines = ["", f"Отклонения наилучшей модели ({best.model.title}):"]
        for row in rows:
            lines.append("   " + "".join(cell.rjust(width) for cell, width in zip(row, widths)))
        return "\n".join(lines)

    @staticmethod
    def _model_equation(result: FitResult) -> str:
        parts = [f"{name} = {format_number(value)}" for name, value in zip(result.model.parameters, result.coefficients)]
        return f"{result.model.formula},   " + ",   ".join(parts)

    def _set_status(self, text: str, success: bool) -> None:
        color = SUCCESS if success else ERROR
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(text)

    @staticmethod
    def _configure_selector_list(widget: QListWidget) -> None:
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setUniformItemSizes(False)
        widget.setWrapping(False)
        widget.setWordWrap(True)
        widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @staticmethod
    def _lock_selector_height(widget: QListWidget, rows: int) -> None:
        height = widget.frameWidth() * 2 + 2
        for index in range(rows):
            row_height = widget.sizeHintForRow(index)
            item_hint = widget.item(index).sizeHint().height()
            height += max(row_height, item_hint, 36)
        widget.setMinimumHeight(height)
        widget.setMaximumHeight(height)


class Lab4QtApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ᓚᘏᗢ Лабораторная работа №4 ᗢᘏᓗ")
        self.resize(1180, 760)
        self.setMinimumSize(1060, 640)
        self.page = Lab4Page()
        self.setCentralWidget(self.page)
        self._apply_styles()
        self.page.adjust_metrics()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {APP_BG};
                color: {TEXT};
            }}
            #SidebarHost {{
                background: {APP_BG};
            }}
            #SidebarScroll {{
                background: {APP_BG};
                border: none;
            }}
            #Card {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            #CardTitle {{
                color: {TEXT};
            }}
            #HintLabel, #StatusLabel {{
                color: {MUTED};
            }}
            QListWidget, QLineEdit, QTextEdit {{
                background: #fffdfa;
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT};
                selection-background-color: #efd7c8;
                selection-color: {TEXT};
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background: #efd7c8;
            }}
            QTableWidget {{
                background: #fffdfa;
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT};
                gridline-color: {BORDER};
                selection-background-color: #efd7c8;
                selection-color: {TEXT};
            }}
            QTableWidget::item {{
                padding: 2px 6px;
            }}
            QHeaderView {{
                background: #f4e5d9;
            }}
            QHeaderView::section {{
                background: #f4e5d9;
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 4px 6px;
            }}
            QTableCornerButton::section {{
                background: #f4e5d9;
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
            }}
            QListWidget::indicator {{
                width: 15px;
                height: 15px;
                margin-right: 6px;
                border: 1px solid {BORDER};
                border-radius: 4px;
                background: #fffdfa;
            }}
            QListWidget::indicator:hover {{
                border-color: {ACCENT};
            }}
            QListWidget::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT_DARK};
            }}
            QPushButton {{
                min-height: 34px;
                border: 1px solid {BORDER};
                border-radius: 6px;
                background: #fffdfa;
                color: {TEXT};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: #f4e5d9;
            }}
            QPushButton:disabled {{
                color: #b3a898;
                background: #faf6ef;
            }}
            QPushButton#PrimaryButton {{
                background: {ACCENT};
                color: white;
                border-color: {ACCENT_DARK};
                font-weight: 600;
            }}
            #RightHost, #RightScroll {{
                background: {APP_BG};
                border: none;
            }}
            QPushButton#PrimaryButton:hover {{
                background: {ACCENT_DARK};
            }}
            """
        )
