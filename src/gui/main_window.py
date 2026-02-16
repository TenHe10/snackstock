from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCompleter,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import EXPIRY_WARNING_DAYS
from src.db_manager import InventoryDB, Product, load_selected_db_path, save_selected_db_path
from src.logic.inbound import InboundService
from src.logic.outbound import OutboundService
from src.logic.report import ReportService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = InventoryDB(load_selected_db_path())
        self.inbound = InboundService(self.db)
        self.outbound = OutboundService(self.db)
        self.report = ReportService(self.db)
        self.cart: dict[str, int] = {}
        self._updating_cart_table = False

        self.setWindowTitle("SnackStock 库存管理")
        self.resize(1180, 760)
        self._build_ui()
        self._init_barcode_completer()
        self.switch_page(0)
        self.refresh_all()
        self.show_startup_warning_popup()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        nav = QHBoxLayout()
        self.inbound_page_btn = QPushButton("入库")
        self.outbound_page_btn = QPushButton("出库")
        self.inventory_page_btn = QPushButton("库存与报表")
        self.page_buttons = [
            self.inbound_page_btn,
            self.outbound_page_btn,
            self.inventory_page_btn,
        ]
        for index, btn in enumerate(self.page_buttons):
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=index: self.switch_page(i))
            nav.addWidget(btn)
        nav.addStretch(1)
        main_layout.addLayout(nav)

        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_inbound_page())
        self.page_stack.addWidget(self._build_outbound_page())
        self.page_stack.addWidget(self._build_inventory_page())
        main_layout.addWidget(self.page_stack)

    def _build_inbound_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._build_product_box(), 0, 0)
        layout.addWidget(self._build_stock_in_box(), 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return page

    def _build_outbound_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._build_stock_out_box(), 0, 0)
        layout.addWidget(self._build_cart_box(), 1, 0)
        layout.setRowStretch(1, 1)
        return page

    def _build_inventory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_inventory_box())
        return page

    def switch_page(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.page_buttons):
            btn.setChecked(i == index)

        if index == 0:
            self.inbound_scan_barcode.setFocus()
        elif index == 1:
            self.manual_barcode_input.setFocus()
        else:
            self.report_date.setFocus()

    def _build_product_box(self) -> QGroupBox:
        box = QGroupBox("商品档案")
        form = QFormLayout(box)

        self.product_barcode = QLineEdit()
        self.product_name = QLineEdit()
        self.product_category = QLineEdit()
        self.product_purchase = QLineEdit("0")
        self.product_retail = QLineEdit("0")
        self.product_min_stock = QSpinBox()
        self.product_min_stock.setRange(0, 999999)
        self.product_min_stock.setValue(5)

        form.addRow("条码", self.product_barcode)
        form.addRow("名称", self.product_name)
        form.addRow("分类", self.product_category)
        form.addRow("进价", self.product_purchase)
        form.addRow("售价", self.product_retail)
        form.addRow("安全库存", self.product_min_stock)

        btn = QPushButton("新增/更新商品")
        btn.clicked.connect(self.save_product)
        form.addRow(btn)
        return box

    def _build_stock_in_box(self) -> QGroupBox:
        box = QGroupBox("入库扫码")
        form = QFormLayout(box)

        self.inbound_scan_barcode = QLineEdit()
        self.inbound_scan_barcode.setPlaceholderText("扫码枪输入后按回车")
        self.inbound_scan_qty = QSpinBox()
        self.inbound_scan_qty.setRange(1, 999999)
        self.inbound_scan_qty.setValue(1)
        self.inbound_scan_batch = QLineEdit()
        self.inbound_scan_expiry = QDateEdit()
        self.inbound_scan_expiry.setCalendarPopup(True)
        self.inbound_scan_expiry.setDate(QDate.currentDate())

        self.btn_stock_in = QPushButton("确认入库")
        self.btn_stock_in.clicked.connect(self.stock_in_once)

        form.addRow("条码", self.inbound_scan_barcode)
        form.addRow("数量", self.inbound_scan_qty)
        form.addRow("批次", self.inbound_scan_batch)
        form.addRow("过期日期", self.inbound_scan_expiry)
        form.addRow(self.btn_stock_in)
        return box

    def _build_stock_out_box(self) -> QGroupBox:
        box = QGroupBox("出库录入")
        form = QFormLayout(box)

        self.manual_barcode_input = QLineEdit()
        self.manual_barcode_input.setPlaceholderText("手动输入条码，按前缀匹配候选")
        self.manual_barcode_input.returnPressed.connect(self.add_manual_once)
        self.manual_barcode_input.textEdited.connect(self._on_manual_barcode_edited)

        self.manual_qty = QSpinBox()
        self.manual_qty.setRange(1, 999999)
        self.manual_qty.setValue(1)

        self.btn_add_manual = QPushButton("手动加入购物车")
        self.btn_add_manual.clicked.connect(self.add_manual_once)

        self.scan_barcode_input = QLineEdit()
        self.scan_barcode_input.setPlaceholderText("扫码枪输入后按回车，直接加入购物车(数量=1)")
        self.scan_barcode_input.returnPressed.connect(self.add_scanned_once)

        form.addRow("手动条码", self.manual_barcode_input)
        form.addRow("手动数量", self.manual_qty)
        form.addRow(self.btn_add_manual)
        form.addRow(QLabel("扫码枪模式"), self.scan_barcode_input)
        return box

    def _build_cart_box(self) -> QGroupBox:
        box = QGroupBox("出库购物车")
        layout = QVBoxLayout(box)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(["条码", "名称", "数量", "单价", "操作"])
        self.cart_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cart_table)

        row = QHBoxLayout()
        self.checkout_btn = QPushButton("结算")
        self.checkout_btn.clicked.connect(self.checkout_cart)
        self.summary_label = QLabel("营业额: 0.00  毛利润: 0.00")
        row.addWidget(self.checkout_btn)
        row.addWidget(self.summary_label)
        layout.addLayout(row)
        return box

    def _build_inventory_box(self) -> QGroupBox:
        box = QGroupBox("库存与报表")
        layout = QVBoxLayout(box)

        db_row = QHBoxLayout()
        self.db_path_label = QLabel()
        self.db_path_label.setWordWrap(True)
        self.btn_select_db = QPushButton("选择数据库文件")
        self.btn_select_db.clicked.connect(self.select_database_file)
        db_row.addWidget(QLabel("当前数据库"))
        db_row.addWidget(self.db_path_label, 1)
        db_row.addWidget(self.btn_select_db)
        layout.addLayout(db_row)

        search_row = QHBoxLayout()
        self.inventory_search = QLineEdit()
        self.inventory_search.setPlaceholderText("搜索条码/名称/分类")
        self.inventory_search.textChanged.connect(self._apply_inventory_filter)
        search_row.addWidget(QLabel("搜索"))
        search_row.addWidget(self.inventory_search, 1)
        layout.addLayout(search_row)

        self.inventory_table = QTableWidget(0, 5)
        self.inventory_table.setHorizontalHeaderLabels(["条码", "名称", "分类", "库存", "安全库存"])
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        self.inventory_table.setSortingEnabled(True)
        layout.addWidget(self.inventory_table)

        self.warning_text = QTextEdit()
        self.warning_text.setReadOnly(True)
        self.warning_text.setPlaceholderText("临期/缺货预警")
        layout.addWidget(self.warning_text)

        self.daily_label = QLabel("日报: 营业额 0.00 / 进货额 0.00 / 毛利润 0.00")
        self.daily_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.daily_label)

        report_row = QHBoxLayout()
        self.report_date = QDateEdit()
        self.report_date.setCalendarPopup(True)
        self.report_date.setDate(QDate.currentDate())
        self.export_btn = QPushButton("导出日报 CSV")
        self.export_btn.clicked.connect(self.export_daily_csv)
        report_row.addWidget(QLabel("报表日期"))
        report_row.addWidget(self.report_date)
        report_row.addWidget(self.export_btn)
        report_row.addStretch(1)
        layout.addLayout(report_row)

        return box

    def _init_barcode_completer(self) -> None:
        self.barcode_completer = QCompleter([], self)
        self.barcode_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.barcode_completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self.barcode_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.manual_barcode_input.setCompleter(self.barcode_completer)

    def refresh_barcode_completer(self) -> None:
        self.barcode_completer.model().setStringList(self.db.list_product_barcodes())

    def _on_manual_barcode_edited(self, text: str) -> None:
        if not text:
            return
        self.barcode_completer.setCompletionPrefix(text)
        self.barcode_completer.complete()

    def select_database_file(self) -> None:
        initial = str(self.db.db_path)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择数据库文件",
            initial,
            "SQLite DB (*.db)",
        )
        if not selected_path:
            return

        target = Path(selected_path)
        try:
            new_db = InventoryDB(target)
        except Exception as exc:
            self._warn(f"数据库切换失败: {exc}")
            return

        self.db = new_db
        self.inbound = InboundService(self.db)
        self.outbound = OutboundService(self.db)
        self.report = ReportService(self.db)
        self.cart.clear()
        save_selected_db_path(target)

        self.refresh_all()
        self._info(f"已切换数据库: {target}")

    def save_product(self) -> None:
        barcode = self.product_barcode.text().strip()
        name = self.product_name.text().strip()
        if not barcode or not name:
            self._warn("条码和名称不能为空")
            return

        try:
            purchase = float(self.product_purchase.text().strip())
            retail = float(self.product_retail.text().strip())
        except ValueError:
            self._warn("价格必须是数字")
            return

        product = Product(
            barcode=barcode,
            name=name,
            category=self.product_category.text().strip(),
            purchase_price=purchase,
            retail_price=retail,
            min_stock=self.product_min_stock.value(),
        )
        self.db.upsert_product(product)
        self._info("商品保存成功")
        self.refresh_all()

    def stock_in_once(self) -> None:
        barcode = self.inbound_scan_barcode.text().strip()
        if not barcode:
            self._warn("请先扫码或输入条码")
            return

        try:
            self.inbound.stock_in(
                barcode=barcode,
                quantity=self.inbound_scan_qty.value(),
                batch_no=self.inbound_scan_batch.text().strip() or None,
                expiry_date=self.inbound_scan_expiry.date().toString("yyyy-MM-dd"),
            )
        except Exception as exc:
            self._warn(str(exc))
            return

        self._info("入库成功")
        self.refresh_all()

    def add_manual_once(self) -> None:
        self._add_to_cart(self.manual_barcode_input.text().strip(), self.manual_qty.value())
        self.manual_barcode_input.clear()

    def add_scanned_once(self) -> None:
        self._add_to_cart(self.scan_barcode_input.text().strip(), 1)
        self.scan_barcode_input.clear()

    def _add_to_cart(self, barcode: str, quantity: int) -> None:
        if not barcode:
            self._warn("请先扫码或输入条码")
            return

        product = self.db.get_product(barcode)
        if not product:
            self.switch_page(0)
            self.product_barcode.setText(barcode)
            self._warn("商品不存在，请先在入库页创建商品档案")
            return

        self.cart[barcode] = self.cart.get(barcode, 0) + max(1, quantity)
        self.refresh_cart_table()

    def _on_cart_qty_changed(self, barcode: str, quantity: int) -> None:
        if self._updating_cart_table:
            return
        if quantity <= 0:
            self.cart.pop(barcode, None)
        else:
            self.cart[barcode] = quantity

    def _remove_cart_item(self, barcode: str) -> None:
        self.cart.pop(barcode, None)
        self.refresh_cart_table()

    def checkout_cart(self) -> None:
        try:
            result = self.outbound.checkout(self.cart)
        except Exception as exc:
            self._warn(str(exc))
            return

        self.cart.clear()
        self.summary_label.setText(f"营业额: {result['revenue']:.2f}  毛利润: {result['profit']:.2f}")
        self._info("结算完成")
        self.refresh_all()

    def refresh_all(self) -> None:
        self.db_path_label.setText(str(self.db.db_path))
        self.refresh_inventory_table()
        self.refresh_cart_table()
        self.refresh_warnings()
        self.refresh_daily_report()
        self.refresh_barcode_completer()

    def refresh_inventory_table(self) -> None:
        rows = self.db.list_products_with_stock()

        self.inventory_table.setSortingEnabled(False)
        self.inventory_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.inventory_table.setItem(r, 0, QTableWidgetItem(row["barcode"]))
            self.inventory_table.setItem(r, 1, QTableWidgetItem(row["name"]))
            self.inventory_table.setItem(r, 2, QTableWidgetItem(row["category"]))
            self.inventory_table.setItem(r, 3, QTableWidgetItem(str(row["current_stock"])))
            self.inventory_table.setItem(r, 4, QTableWidgetItem(str(row["min_stock"])))
        self.inventory_table.setSortingEnabled(True)

        self._apply_inventory_filter(self.inventory_search.text())

    def _apply_inventory_filter(self, keyword: str) -> None:
        normalized = keyword.strip().lower()
        for r in range(self.inventory_table.rowCount()):
            if not normalized:
                self.inventory_table.setRowHidden(r, False)
                continue

            values = [
                self.inventory_table.item(r, 0).text() if self.inventory_table.item(r, 0) else "",
                self.inventory_table.item(r, 1).text() if self.inventory_table.item(r, 1) else "",
                self.inventory_table.item(r, 2).text() if self.inventory_table.item(r, 2) else "",
            ]
            matched = any(normalized in value.lower() for value in values)
            self.inventory_table.setRowHidden(r, not matched)

    def refresh_cart_table(self) -> None:
        barcodes = list(self.cart.keys())

        self._updating_cart_table = True
        try:
            self.cart_table.setRowCount(len(barcodes))
            for r, barcode in enumerate(barcodes):
                product = self.db.get_product(barcode)
                name = product["name"] if product else "未知商品"
                price = float(product["retail_price"]) if product else 0.0
                qty = int(self.cart[barcode])

                self.cart_table.setItem(r, 0, QTableWidgetItem(barcode))
                self.cart_table.setItem(r, 1, QTableWidgetItem(name))
                self.cart_table.setItem(r, 3, QTableWidgetItem(f"{price:.2f}"))

                qty_spin = QSpinBox()
                qty_spin.setRange(1, 999999)
                qty_spin.setValue(max(1, qty))
                qty_spin.valueChanged.connect(
                    lambda value, b=barcode: self._on_cart_qty_changed(b, value)
                )
                self.cart_table.setCellWidget(r, 2, qty_spin)

                remove_btn = QPushButton("移除")
                remove_btn.clicked.connect(lambda _, b=barcode: self._remove_cart_item(b))
                self.cart_table.setCellWidget(r, 4, remove_btn)
        finally:
            self._updating_cart_table = False

    def refresh_warnings(self) -> None:
        _, _, lines = self._collect_warnings()
        self.warning_text.setText("\n".join(lines))

    def refresh_daily_report(self) -> None:
        report = self.report.daily_report()
        self.daily_label.setText(
            f"日报: 营业额 {report['revenue']:.2f} / 进货额 {report['purchase_cost']:.2f} / 毛利润 {report['gross_profit']:.2f}"
        )

    def _warn(self, msg: str) -> None:
        QMessageBox.warning(self, "提示", msg)

    def _info(self, msg: str) -> None:
        QMessageBox.information(self, "提示", msg)

    def show_startup_warning_popup(self) -> None:
        low_stock, expiring, lines = self._collect_warnings()
        if not low_stock and not expiring:
            return
        QMessageBox.warning(self, "启动预警", "\n".join(lines))

    def _collect_warnings(self) -> tuple[list, list, list[str]]:
        low_stock = self.db.get_low_stock_products()
        expiring = self.db.get_expiring_batches(within_days=EXPIRY_WARNING_DAYS)

        lines: list[str] = []
        if low_stock:
            lines.append("缺货预警:")
            for row in low_stock:
                lines.append(
                    f"- {row['name']}({row['barcode']}) 库存 {row['current_stock']} < 安全库存 {row['min_stock']}"
                )
        if expiring:
            if lines:
                lines.append("")
            lines.append(f"临期预警({EXPIRY_WARNING_DAYS}天内):")
            for row in expiring:
                lines.append(
                    f"- {row['name']} 批次 {row['batch_no']} 到期 {row['expiry_date']} 剩余 {row['current_qty']}"
                )
        if not lines:
            lines.append("暂无预警")
        return low_stock, expiring, lines

    def export_daily_csv(self) -> None:
        selected = self.report_date.date().toPyDate()
        folder = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not folder:
            return

        try:
            path = self.report.export_daily_report_csv(
                for_date=selected,
                output_dir=folder,
            )
        except Exception as exc:
            self._warn(f"导出失败: {exc}")
            return

        self._info(f"导出成功: {path}")
