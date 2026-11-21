# ui-drag-snap

## 题面

画布拖拽加了智能吸附后，元素贴边就抖、尺寸还莫名被拉长：只取左上角，右/下边不吸附；中心线按外框算，偏半像素；参考线不去重，重复吸附抖动；取第一个在阈值内的而不是最近的，吸附跳；等间距用固定 10 px，忽略 spacing 参数；轴向冲突都应用，两个方向同时跳；应用偏移改变尺寸，矩形拉伸；阈值超出范围不校验，永远吸附；批量共用参考列表，事件之间串；参考包含自身，永远吸附到自己。dragsnap/guides.py 是核心，tests/test_guides.py 15个红。要修的是：修复上述 10 个吸附缺陷，让 15 条测试全部转绿。

## 运行方式

在仓库根目录执行：

```bash
python -m pytest tests -q
```

初始状态必须恰好为 `15 failed`，且不能出现 collection error、import error 或 syntax error；这些失败应全部来自 `dragsnap/guides.py` 中的未实现桩。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## tests 不可修改

`tests/test_guides.py` 是验收依据，不可修改、不可删除、不可跳过。实现只能改 `dragsnap/` 下的代码，让现有 15 条测试自然转绿。

## 文件结构

```text
ui-drag-snap/
├── README.md
├── conftest.py
├── .gitignore
├── dragsnap/
│   ├── __init__.py
│   └── guides.py
└── tests/
    └── test_guides.py
```
