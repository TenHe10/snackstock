from src.db_manager import InventoryDB


class InboundService:
    def __init__(self, db: InventoryDB):
        self.db = db

    def stock_in(
        self,
        barcode: str,
        quantity: int,
        batch_no: str | None = None,
        expiry_date: str | None = None,
    ) -> None:
        self.db.stock_in(
            barcode=barcode,
            quantity=quantity,
            stock_type="采购",
            batch_no=batch_no,
            expiry_date=expiry_date,
        )
