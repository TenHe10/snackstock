from src.db_manager import CartItem, InventoryDB


class OutboundService:
    def __init__(self, db: InventoryDB):
        self.db = db

    def checkout(self, cart: dict[str, int]) -> dict[str, float]:
        items = [CartItem(barcode=barcode, quantity=qty) for barcode, qty in cart.items()]
        return self.db.stock_out(items, stock_type="销售")
