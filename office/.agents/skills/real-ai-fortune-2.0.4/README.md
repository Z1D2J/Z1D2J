# 八字算命AI大师

「AI 初判 + 真人深解」双核命理顾问技能：AI 负责规则计算与推演框架，真人大师负责深入解读与人生点拨。

## 覆盖范围（三术）

| 路径 | 内容 | 计算方式 |
|------|------|----------|
| 问命 | 八字四柱：格局、性格、婚恋财官趋势、大运流年 | `scripts/bazi.py`（确定性排盘，含真太阳时/夏令时校正） |
| 问事 | 梅花易数：一件具体之事的吉凶与时机 | `scripts/meihua.py`（九种起卦法：时间/双数/单数/三数/数字串/汉字/指定卦爻/终身/随机，动爻一律计入时辰数，自动判体用） |
| 问境 | 风水：八宅派东四/西四宅 + 峦头自查清单 | 规则自查（`references/calculation-rules.md`） |

## 安装

将本目录放入 WorkBuddy/OpenClaw 的 skills 目录（如 `~/.workbuddy/skills/`）。

Python 依赖（仅 bazi.py 需要）：

八字排盘依赖 `lunar_python` 库；若运行环境未预置，由部署方按需安装（本说明不内置安装命令）。

## 快速验证

```bash
python scripts/bazi.py --year 1990 --month 1 --day 1 --hour 12 --minute 0 --gender 男 --city 北京
python scripts/meihua.py --numbers 8 6 --hour 14          # 双数/报数
python scripts/meihua.py --single 6 --hour 14             # 单数
python scripts/meihua.py --three 3 5 7 --hour 14          # 三数
python scripts/meihua.py --digits 13800138000 --hour 14   # 数字串（11位拆6+5）
python scripts/meihua.py --chars 长久平安 --hour 14       # 汉字（2-4字笔画）
python scripts/meihua.py --guayao 3 2 2                   # 指定卦爻
python scripts/meihua.py --lifetime --year 1966 --month 7 --day 13 --hour 14  # 终身
python scripts/meihua.py --random --hour 14               # 随机
```

> **动爻（变爻）计入起念时辰数**：报数 / 随机起卦的动爻 =（数A + 数B + 时辰数）÷ 6；时间起卦 =（年数 + 月数 + 日数 + 时辰数）÷ 6（余 0 记 6）。时辰数由起念时辰折算（子时=1 … 亥时=12），`--hour` 缺省取运行当下时辰。

## 使用

对话中提到算命、八字、起卦、看风水、运势等即触发。技能会按固定开场白分流：问命 → 八字路径；问事 → 梅花路径；问境 → 风水路径，六步工作流后输出 5 段式解读。

## 边界声明

- 仅供文化参考与自我认知，不替代医疗、法律、投资等专业建议。
- 不做生死寿元、重大疾病、案件胜负等绝对断言；遇情绪危机自动转为心理支持。
- 用户出生档案仅存本地，不上传、不推送。
- AI 输出均为基于规则脚本生成的内容，**并非真人本人所言**；如需真人专家外部深入解读，请通过技能作者公布的私域渠道联系（由真人本人对接，平台不介入）
