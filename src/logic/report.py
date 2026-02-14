from datetime import date
from pathlib import Path
import csv

from config import REPORTS_DIR
from src.db_manager import InventoryDB


class ReportService:
    def __init__(self, db: InventoryDB):
        self.db = db

    def daily_report(self, for_date: date | None = None) -> dict[str, float]:
        return self.db.get_daily_summary(for_date=for_date)

    def export_daily_report_csv(
        self,
        for_date: date | None = None,
        output_dir: Path | str | None = None,
    ) -> Path:
        day = for_date or date.today()
        summary = self.db.get_daily_summary(for_date=day)
        transactions = self.db.get_daily_transactions(for_date=day)

        target_dir = Path(output_dir) if output_dir else REPORTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"daily_report_{day.isoformat()}.csv"

        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["日期", day.isoformat()])
            writer.writerow(["营业额", f"{summary['revenue']:.2f}"])
            writer.writerow(["进货额", f"{summary['purchase_cost']:.2f}"])
            writer.writerow(["毛利润", f"{summary['gross_profit']:.2f}"])
            writer.writerow([])
            writer.writerow(
                ["时间", "类型", "条码", "商品", "数量变动", "进价", "售价", "金额影响(销售额口径)"]
            )

            for row in transactions:
                amount = 0.0
                if row["type"] == "销售":
                    amount = -float(row["change_qty"]) * float(row["retail_price"])
                writer.writerow(
                    [
                        row["timestamp"],
                        row["type"],
                        row["barcode"],
                        row["name"],
                        row["change_qty"],
                        f"{float(row['purchase_price']):.2f}",
                        f"{float(row['retail_price']):.2f}",
                        f"{amount:.2f}",
                    ]
                )
        return path
