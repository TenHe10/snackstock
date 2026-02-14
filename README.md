# SnackStock

SnackStock 是一个面向零食门店的本地桌面库存管理系统（MVP）。

## 已实现能力

- 商品档案管理（新增/更新）
- 扫码入库（记录采购日志，可带批次和过期日期）
- 扫码加入出库购物车、结算扣减库存
- 批次库存按到期日优先扣减（FIFO-by-expiry）
- 低库存预警
- 临期预警（默认 15 天内）
- 启动时预警弹窗汇总
- 当日营业额/进货额/毛利润统计
- 日报 CSV 导出（可选日期）
- 分功能页面切换（入库 / 出库 / 库存与报表）

## 技术栈

- Python 3.13
- PyQt6
- SQLite

## 运行方式

```bash
uv sync
uv run python main.py
```

日报导出会在你选择的目录生成：`daily_report_YYYY-MM-DD.csv`。

## 项目结构

```text
SnackStock/
├── main.py
├── config.py
├── database/
│   ├── inventory.db
│   └── schema.sql
└── src/
    ├── db_manager.py
    ├── scanner_handler.py
    ├── logic/
    │   ├── inbound.py
    │   ├── outbound.py
    │   └── report.py
    └── gui/
        └── main_window.py
```
