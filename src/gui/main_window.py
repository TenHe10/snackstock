from __future__ import annotations

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
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
from src.db_manager import InventoryDB, Product
from src.logic.inbound import InboundService
from src.logic.outbound import OutboundService
from src.logic.report import ReportService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = InventoryDB()
        self.inbound = InboundService(self.db)
        self.outbound = OutboundService(self.db)
        self.report = ReportService(self.db)
        self.cart: dict[str, int] = {}

        self.setWindowTitle("SnackStock 库存管理")
        self.resize(1100, 720)
        self._build_ui()
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
        layout.addWidget(self._build_stock_out_scan_box(), 0, 0)
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
            self.outbound_scan_barcode.setFocus()
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

    def _build_stock_out_scan_box(self) -> QGroupBox:
        box = QGroupBox("出库扫码")
        form = QFormLayout(box)

        self.outbound_scan_barcode = QLineEdit()
        self.outbound_scan_barcode.setPlaceholderText("扫码枪输入后按回车，自动加入购物车")
        self.outbound_scan_barcode.returnPressed.connect(self.add_cart_once)
        self.outbound_scan_qty = QSpinBox()
        self.outbound_scan_qty.setRange(1, 999999)
        self.outbound_scan_qty.setValue(1)

        self.btn_add_cart = QPushButton("加入购物车")
        self.btn_add_cart.clicked.connect(self.add_cart_once)

        form.addRow("条码", self.outbound_scan_barcode)
        form.addRow("数量", self.outbound_scan_qty)
        form.addRow(self.btn_add_cart)
        return box

    def _build_cart_box(self) -> QGroupBox:
        box = QGroupBox("出库购物车")
        layout = QVBoxLayout(box)

        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["条码", "名称", "数量", "单价"])
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
        box = QGroupBox("库存与预警")
        layout = QVBoxLayout(box)

        self.inventory_table = QTableWidget(0, 5)
        self.inventory_table.setHorizontalHeaderLabels(["条码", "名称", "分类", "库存", "安全库存"])
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
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

    def add_cart_once(self) -> None:
        barcode = self.outbound_scan_barcode.text().strip()
        if not barcode:
            self._warn("请先扫码或输入条码")
            return
        product = self.db.get_product(barcode)
        if not product:
            self.switch_page(0)
            self.product_barcode.setText(barcode)
            self._warn("商品不存在，请先在入库页创建商品档案")
            return

        self.cart[barcode] = self.cart.get(barcode, 0) + self.outbound_scan_qty.value()
        self.refresh_cart_table()
        self.outbound_scan_barcode.clear()

    def checkout_cart(self) -> None:
        try:
            result = self.outbound.checkout(self.cart)
        except Exception as exc:
            self._warn(str(exc))
            return
        self.cart.clear()
        self.summary_label.setText(
            f"营业额: {result['revenue']:.2f}  毛利润: {result['profit']:.2f}"
        )
        self._info("结算完成")
        self.refresh_all()

    def refresh_all(self) -> None:
        self.refresh_inventory_table()
        self.refresh_cart_table()
        self.refresh_warnings()
        self.refresh_daily_report()

    def refresh_inventory_table(self) -> None:
        rows = self.db.list_products_with_stock()
        self.inventory_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.inventory_table.setItem(r, 0, QTableWidgetItem(row["barcode"]))
            self.inventory_table.setItem(r, 1, QTableWidgetItem(row["name"]))
            self.inventory_table.setItem(r, 2, QTableWidgetItem(row["category"]))
            self.inventory_table.setItem(r, 3, QTableWidgetItem(str(row["current_stock"])))
            self.inventory_table.setItem(r, 4, QTableWidgetItem(str(row["min_stock"])))

    def refresh_cart_table(self) -> None:
        barcodes = list(self.cart.keys())
        self.cart_table.setRowCount(len(barcodes))
        for r, barcode in enumerate(barcodes):
            product = self.db.get_product(barcode)
            name = product["name"] if product else "未知商品"
            price = float(product["retail_price"]) if product else 0.0
            qty = self.cart[barcode]
            self.cart_table.setItem(r, 0, QTableWidgetItem(barcode))
            self.cart_table.setItem(r, 1, QTableWidgetItem(name))
            self.cart_table.setItem(r, 2, QTableWidgetItem(str(qty)))
            self.cart_table.setItem(r, 3, QTableWidgetItem(f"{price:.2f}"))

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
