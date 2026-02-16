# SnackStock

SnackStock 是一个面向零食门店的本地桌面库存管理系统（MVP）。

## 已实现能力

- 商品档案管理（新增/更新）
- 扫码入库（记录采购日志，可带批次和过期日期）
- 出库双模式：
  - 手动输入条码（前缀候选下拉）
  - 扫码枪录入（扫描一次直接加入购物车，数量默认 1）
- 购物车自动合并同类商品，并支持在表格内直接修改数量
- 库存列表搜索与排序
- 批次库存按到期日优先扣减（FIFO-by-expiry）
- 低库存预警
- 临期预警（默认 15 天内）
- 启动时预警弹窗汇总
- 当日营业额/进货额/毛利润统计
- 日报 CSV 导出（可选日期）
- 支持在 UI 中切换数据库文件
- 库存变动日志按月份自动拆分为归档文件，降低主数据库体积增长速度

## 技术栈

- Python 3.13
- PyQt6
- SQLite

## 开发与发布约定

- 开发环境：macOS（写代码、提交代码）
- 生产环境：Windows（拉取代码、打包、运行）
- 当前阶段：暂不实现程序自动更新，采用手动发布

## 开发运行方式（macOS）

```bash
uv sync
uv run python main.py
```

## Windows 打包（生产机）

```bash
build_windows.bat
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
