# -*- coding: utf-8 -*-
"""
meihua.py - 梅花易数起卦（先天八卦数）

依赖：lunar_python（仅用于公历->农历，以便"按时间起卦"取农历年月日时）
      安装：C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/pip.exe install lunar_python

用法：
  # ① 时间法 · 邵雍古法（默认，取农历年月日时辰）
  python meihua.py --year 2024 --month 7 --day 3 --hour 14 --minute 30
  # ① 时间法 · 现代时间（直接用小时数作上卦、分钟数作下卦）
  python meihua.py --modern --hour 14 --minute 30
  # ② 报数法（可标注 随性/灵性 心法）
  python meihua.py --baoshu 8 6 --xin 灵性
  # ③ 随机法
  python meihua.py --random
  # ④ 指定法（可给手机号等长数字，自动拆成两数）
  python meihua.py --zhiding 13800138000
  # ⑤ 终身起卦（出生年月日时）
  python meihua.py --lifetime --year 1966 --month 7 --day 13 --hour 14
  # ⑥ 单数起卦
  python meihua.py --single 6
  # ⑦ 三数起卦
  python meihua.py --three 3 5 7
  # ⑧ 数字起卦（3-16 位连续数字，11 位拆 6+5）
  python meihua.py --digits 13800138000
  # ⑨ 汉字起卦（2-4 字笔画）
  python meihua.py --chars 长久平安
  # ⑩ 指定起卦（上卦 下卦 动爻）
  python meihua.py --guayao 3 2 2
  # 生成 PNG 图片（类似手机排盘软件效果）
  python meihua.py --baoshu 8 6 --image output.png
  # 仅输出纯文字
  python meihua.py --baoshu 8 6 --text-only

规则（先天八卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8）：
  ① 邵雍古法：年取地支序数(1-12)、月取农历月数、日取农历日、时取时辰序数(1-12)
            上卦=(年+月+日)%8，下卦=(年+月+日+时)%8，动爻=(年+月+日+时)%6
  ① 现代时间：上卦=小时%8，下卦=分钟%8，动爻=(小时+分钟)%6（直接用时钟数，不取时辰）
  ② 报数法：上卦=A%8，下卦=B%8，动爻=(A+B+时辰数)%6（A、B 为用户所报两数）
  ③ 随机法：随机取两数 A、B，动爻=(A+B+时辰数)%6
  ④ 指定法：用户指定的数字（手机号等），自动拆成前后两半作 A、B，动爻=(A+B+时辰数)%6
  ⑤ 终身起卦：用出生年月日时，规则同邵雍古法
  ⑥ 单数起卦：上=N%8，下=(N+时辰数)%8，动=(N+时辰数)%6（一数加时成卦）
  ⑦ 三数起卦：上=A%8，下=B%8，动=(A+B+C+时辰数)%6
  ⑧ 数字起卦：前段各位数字之和%8 为上卦，后段之和%8 为下卦，动=(两段和+时辰数)%6
              （11 位拆前 6 后 5，偶数位对半拆；支持 3-16 位）
  ⑨ 汉字起卦：2/3字 上=第1字笔画 下=第2字笔画；4字 上=前两字笔画和 下=后两字笔画和；
              动=(笔画总和+时辰数)%6（笔画数据 strokes.json 与脚本同目录）
  ⑩ 指定起卦：直接指定上卦数、下卦数、动爻数（不取余、不加时辰）
  ★ 除「时间/现代时间/终身/指定卦爻」外，其余各法动爻一律计入「时辰数」——
    起念时辰折算为 1-12 之数（23:00-00:59 子时=1，01:00-02:59 丑时=2，…余 0 记 8/6）。
    默认取起卦当时的系统时间，可用 --hour 指定起念时刻以便复核。
  体用：动爻所在之卦为「用」，无动爻之卦为「体」。

仅作规则推演参考，最终判断请结合处境或咨询真人大师。
"""
import argparse
import os
import sys
import datetime
import random

try:
    import lunar_python as L
except ImportError:
    sys.stderr.write(
        "ERROR: 缺少 lunar_python。请安装：\n"
        "  .../envs/default/Scripts/pip.exe install lunar_python\n"
    )
    sys.exit(2)

# 先天八卦
XIANTIAN = {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 8: "坤"}
ZHI_ORDER = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZHI_NUM = {z: i + 1 for i, z in enumerate(ZHI_ORDER)}  # 子1..亥12

# 卦数 <-> 3位二进制（bit2=上爻, bit1=中爻, bit0=初爻）
# 标准先天八卦爻象：乾三阳111 / 兑上缺011 / 离中虚101 / 震仰盂001
#                   巽下断110 / 坎中满010 / 艮覆碗100 / 坤三阴000
NUM_BITS = {1: 0b111, 2: 0b011, 3: 0b101, 4: 0b001, 5: 0b110, 6: 0b010, 7: 0b100, 8: 0b000}
BITS_NUM = {v: k for k, v in NUM_BITS.items()}

# 六十四卦名 (上卦数, 下卦数) -> 卦名
GUA_NAME = {
    (1, 1): "乾为天", (1, 2): "天泽履", (1, 3): "天火同人", (1, 4): "天雷无妄",
    (1, 5): "天风姤", (1, 6): "天水讼", (1, 7): "天山遁", (1, 8): "天地否",
    (2, 1): "泽天夬", (2, 2): "兑为泽", (2, 3): "泽火革", (2, 4): "泽雷随",
    (2, 5): "泽风大过", (2, 6): "泽水困", (2, 7): "泽山咸", (2, 8): "泽地萃",
    (3, 1): "火天大有", (3, 2): "火泽睽", (3, 3): "离为火", (3, 4): "火雷噬嗑",
    (3, 5): "火风鼎", (3, 6): "火水未济", (3, 7): "火山旅", (3, 8): "火地晋",
    (4, 1): "雷天大壮", (4, 2): "雷泽归妹", (4, 3): "雷火丰", (4, 4): "震为雷",
    (4, 5): "雷风恒", (4, 6): "雷水解", (4, 7): "雷山小过", (4, 8): "雷地豫",
    (5, 1): "风天小畜", (5, 2): "风泽中孚", (5, 3): "风火家人", (5, 4): "风雷益",
    (5, 5): "巽为风", (5, 6): "风水涣", (5, 7): "风山渐", (5, 8): "风地观",
    (6, 1): "水天需", (6, 2): "水泽节", (6, 3): "水火既济", (6, 4): "水雷屯",
    (6, 5): "水风井", (6, 6): "坎为水", (6, 7): "水山蹇", (6, 8): "水地比",
    (7, 1): "山天大畜", (7, 2): "山泽损", (7, 3): "山火贲", (7, 4): "山雷颐",
    (7, 5): "山风蛊", (7, 6): "山水蒙", (7, 7): "艮为山", (7, 8): "山地剥",
    (8, 1): "地天泰", (8, 2): "地泽临", (8, 3): "地火明夷", (8, 4): "地雷复",
    (8, 5): "地风升", (8, 6): "地水师", (8, 7): "地山谦", (8, 8): "坤为地",
}


def bit_to_num(bits):
    return BITS_NUM[bits & 0b111]


def num_to_bits(n):
    return NUM_BITS[n]


def trigram_reverse(n):
    """先天卦反象：阴阳全反，数 = 9 - n"""
    return 9 - n


def mod8(x):
    """把任意整数映射到 1-8 的卦序数（0 归 8）"""
    return (int(x) - 1) % 8 + 1


def mod6(x):
    """把任意整数映射到 1-6 的动爻序（0 归 6）"""
    return (int(x) % 6) or 6


def hour_to_shi(hour):
    """小时(0-23) -> 时辰序数(1-12，子=1)"""
    if hour == 23 or hour == 0:
        return 1
    return ZHI_NUM[ZHI_ORDER[(hour + 1) // 2 % 12]]


def shi_name(snum):
    """时辰序数 -> 时辰名（子时 / 丑时 / …）"""
    return ZHI_ORDER[(snum - 1) % 12] + "时"


def split_long_number(n):
    """指定法：单个数（如手机号）按中点拆成前后两半，分别作 A、B"""
    s = str(int(n))
    if len(s) <= 2:
        return [int(s), int(s)]
    mid = (len(s) + 1) // 2
    return [int(s[:mid]), int(s[mid:])]


# ---------------- 汉字笔画（strokes.json 与本脚本同目录） ----------------
_STROKES = None


def _load_strokes():
    global _STROKES
    if _STROKES is not None:
        return _STROKES
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strokes.json")
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            _STROKES = json.load(f)
    except Exception:
        _STROKES = {}
    return _STROKES


def hanzi_strokes_list(chars):
    """字符串 -> 每字笔画数列表；有生僻字查不到时抛 ValueError"""
    out = []
    for ch in chars:
        n = _load_strokes().get(ch)
        if n is None:
            raise ValueError("汉字「%s」笔画数未收录，请换常用字或改用其他起卦法" % ch)
        out.append(int(n))
    return out


def hexa_from_pair(up, down):
    """返回六爻列表，index0=顶爻（上卦上爻），index5=初爻（下卦初爻）"""
    ub = num_to_bits(up)
    db = num_to_bits(down)
    return [(ub >> 2) & 1, (ub >> 1) & 1, ub & 1,
            (db >> 2) & 1, (db >> 1) & 1, db & 1]


def pair_from_hexa(bits):
    """六爻列表（顶->底）转回 (上卦数, 下卦数)"""
    up = bit_to_num((bits[0] << 2) | (bits[1] << 1) | bits[2])
    down = bit_to_num((bits[3] << 2) | (bits[4] << 1) | bits[5])
    return (up, down)


def zong_gua(up, down):
    """综卦：六爻整体倒置"""
    return pair_from_hexa(list(reversed(hexa_from_pair(up, down))))


def cuo_gua(up, down):
    """错卦：每爻阴阳全反"""
    bits = hexa_from_pair(up, down)
    return pair_from_hexa([b ^ 1 for b in bits])


# 卦画渲染（文本版）
YAO_WIDTH = 13  # 单爻宽度（字符）
YANG = "━" * YAO_WIDTH
YIN = "━" * (YAO_WIDTH // 2 - 1) + "　" + "━" * (YAO_WIDTH // 2 - 1)


def render_pair(up, down):
    """渲染一个六爻卦，返回 8 行字符串（顶空行 + 6 爻 + 底卦名），顶爻在上"""
    bits = hexa_from_pair(up, down)
    rows = [YANG if b else YIN for b in bits]
    name = GUA_NAME.get((up, down), "")
    out = ["".center(YAO_WIDTH)]
    out.extend(rows)
    out.append(name.center(YAO_WIDTH))
    return out


def render_panel(g):
    """把本卦/互卦/变卦/综卦/错卦并排成一张图"""
    items = [
        ("本卦", g["本卦"]),
        ("互卦", g["互卦"]),
        ("变卦", g["变卦"]),
        ("综卦", g["综卦"]),
        ("错卦", g["错卦"]),
    ]
    col_w = YAO_WIDTH + 4
    # 表头
    header = "  ".join([lab.center(col_w) for lab, _ in items])
    # 爻行
    rendered = [render_pair(up, down) for _, (up, down) in items]
    body_lines = []
    for i in range(8):  # render_pair 返回 8 行：空行、卦名空行、6爻、卦名
        row = "  ".join([col[i].center(col_w) for col in rendered])
        body_lines.append(row)
    return header + "\n" + "\n".join(body_lines)


def _load_font(size):
    """按系统字体回退加载中文字体"""
    from PIL import ImageFont
    candidates = [
        r"C:/Windows/Fonts/msyh.ttc",
        r"C:/Windows/Fonts/simsun.ttc",
        r"C:/Windows/Fonts/simhei.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_image(r, out_path):
    """生成类似手机排盘软件的 PNG 图片（参考附图风格）"""
    from PIL import Image, ImageDraw

    W, H = 800, 670
    BG = "#FFF8F5"
    RED = "#C45C5C"
    TXT = "#333333"
    LINE = "#1A1A1A"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _load_font(26)
    f_header = _load_font(18)
    f_body = _load_font(16)
    f_small = _load_font(14)

    # 顶部红条标题
    draw.rectangle([0, 0, W, 56], fill=RED)
    title = "梅花易数卦象图"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 14), title, fill="white", font=f_title)

    # 「起卦时间」板块：红条标题 + 六行信息
    y = 72
    draw.rectangle([0, y, W, y + 30], fill=RED)
    bar = "起卦时间"
    bbox = draw.textbbox((0, 0), bar, font=f_header)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y + 4), bar, fill="white", font=f_header)
    y += 30 + 12
    x = 40
    line_h = 27
    info = [
        ("公历", r.get("公历", "")),
        ("阴历", r.get("阴历", "")),
        ("四柱", r.get("四柱", "")),
        ("旬空", r.get("旬空", "")),
        ("起卦", r.get("起卦", "")),
        ("取数", r.get("取数", "")),
        ("动爻", "第 %d 爻" % r["动爻"]),
    ]
    for lab, val in info:
        draw.text((x, y), lab + "：", fill=RED, font=f_body)
        draw.text((x + 64, y), val, fill=TXT, font=f_body)
        y += line_h
    y += 14

    # 分隔条
    draw.rectangle([30, y, W - 30, y + 34], fill=RED)
    bar_text = "梅花易数卦象"
    bbox = draw.textbbox((0, 0), bar_text, font=f_header)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y + 6), bar_text, fill="white", font=f_header)
    y += 48

    # 卦画区：五列
    labels = ["本卦", "互卦", "变卦", "综卦", "错卦"]
    raw = r.get("_raw", {})
    pairs = [raw.get(k, (1, 1)) for k in ["本卦", "互卦", "变卦", "综卦", "错卦"]]
    n_cols = len(labels)
    col_w = 132
    gap = 18
    start_x = (W - (n_cols * col_w + (n_cols - 1) * gap)) // 2

    yao_h = 32
    yao_th = 16          # 爻线厚度（厚重感）
    yao_top = y + 30
    for ci, (lab, pair) in enumerate(zip(labels, pairs)):
        cx = start_x + ci * (col_w + gap)
        # 列标题
        bbox = draw.textbbox((0, 0), lab, font=f_header)
        tw = bbox[2] - bbox[0]
        draw.text((cx + (col_w - tw) // 2, y), lab, fill=RED, font=f_header)
        # 六爻（顶在上）
        bits = hexa_from_pair(pair[0], pair[1])
        for i, b in enumerate(bits):
            yy = yao_top + i * yao_h
            top = yy + (yao_h - yao_th) // 2
            bot = yy + (yao_h + yao_th) // 2
            if b:  # 阳爻（整条）
                draw.rectangle([cx + 8, top, cx + col_w - 8, bot], fill=LINE)
            else:  # 阴爻（两段，中间留空）
                seg = (col_w - 16) // 2 - 10
                draw.rectangle([cx + 8, top, cx + 8 + seg, bot], fill=LINE)
                draw.rectangle([cx + col_w - 8 - seg, top, cx + col_w - 8, bot], fill=LINE)
        # 卦名
        name = GUA_NAME.get(pair, "")
        bbox = draw.textbbox((0, 0), name, font=f_header)
        tw = bbox[2] - bbox[0]
        draw.text((cx + (col_w - tw) // 2, yao_top + 6 * yao_h + 8), name, fill=TXT, font=f_header)
        # 上/下卦小字
        sub = "上%s下%s" % (XIANTIAN[pair[0]], XIANTIAN[pair[1]])
        bbox = draw.textbbox((0, 0), sub, font=f_small)
        tw = bbox[2] - bbox[0]
        draw.text((cx + (col_w - tw) // 2, yao_top + 6 * yao_h + 34), sub, fill="#666666", font=f_small)

    img.save(out_path)
    return out_path


def time_to_yue_ri_shi(year, month, day, hour):
    """公历 -> 农历 年地支序数 / 月 / 日 / 时辰序数"""
    sol = L.Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lun = L.Lunar.fromSolar(sol)
    year_zhi = lun.getYearZhi()           # 地支字
    ynum = ZHI_NUM.get(year_zhi, 1)
    mnum = abs(lun.getMonth())           # 农历月（闰月取绝对值）
    dnum = lun.getDay()                  # 农历日
    # 时辰：23-1子,1-3丑,...
    if hour == 23 or hour == 0:
        snum = 1
    else:
        snum = ZHI_NUM[ZHI_ORDER[(hour + 1) // 2 % 12]]
    return ynum, mnum, dnum, snum


GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
GANZHI = [GAN[i % 10] + ZHI[i % 12] for i in range(60)]  # 0=甲子


def year_ganzhi_lichun(year, month, day):
    """年柱以立春为界（干支历/八字惯例），非春节。
    干支年序号 = (year - 4) % 60（公元4年=甲子），立春前归上一年。"""
    jq = L.Lunar.fromYmd(year, 1, 1).getJieQiTable()
    lc = jq.get("立春")
    gy = year
    if lc and (month, day) < (lc.getMonth(), lc.getDay()):
        gy = year - 1
    return GANZHI[(gy - 4) % 60]


def compute_time_info(year, month, day, hour, minute):
    """返回 (公历, 阴历, 四柱, 旬空) 字符串"""
    sol = L.Solar.fromYmdHms(year, month, day, hour, minute, 0)
    lun = L.Lunar.fromSolar(sol)
    gz_year = year_ganzhi_lichun(year, month, day)
    gz_month = lun.getMonthInGanZhi()
    gz_day = lun.getDayInGanZhi()
    gz_time = lun.getTimeInGanZhi()
    ganzhi = "%s %s %s %s" % (gz_year, gz_month, gz_day, gz_time)
    xunkong = lun.getDayXunKong()
    lunar_str = "%s年%s月%s %s时" % (gz_year, lun.getMonthInChinese(),
                                     lun.getDayInChinese(), lun.getTimeZhi())
    greg = "%04d-%02d-%02d %02d:%02d" % (year, month, day, hour, minute)
    return greg, lunar_str, ganzhi, xunkong


def build_gua(up, down, dong):
    """由上下卦数、动爻(1-6)推本卦/变卦/互卦及体用"""
    # 本卦六爻（顶->底）
    ub = num_to_bits(up)
    db = num_to_bits(down)
    lines = [(ub >> 2) & 1, (ub >> 1) & 1, ub & 1, (db >> 2) & 1, (db >> 1) & 1, db & 1]
    # 动爻位置 p(1=初..6=上) -> 翻转 lines[6-p]
    p = dong
    lines2 = list(lines)
    lines2[6 - p] ^= 1
    # 变卦上下
    up2 = bit_to_num((lines2[0] << 2) | (lines2[1] << 1) | lines2[2])
    down2 = bit_to_num((lines2[3] << 2) | (lines2[4] << 1) | lines2[5])
    # 互卦：下互=本卦二三四爻(新初=二爻,新中=三爻,新上=四爻)；
    #       上互=本卦三四五爻(新初=三爻,新中=四爻,新上=五爻)
    hu_down = bit_to_num((lines[2] << 2) | (lines[3] << 1) | lines[4])
    hu_up = bit_to_num((lines[1] << 2) | (lines[2] << 1) | lines[3])
    # 体用：动爻在下(1-3)=下卦为用；在上(4-6)=上卦为用
    if p <= 3:
        ti, yong = up, down        # 体=上(静), 用=下(动)
    else:
        ti, yong = down, up        # 体=下(静), 用=上(动)
    return {
        "本卦": (up, down), "变卦": (up2, down2), "互卦": (hu_up, hu_down),
        "综卦": zong_gua(up, down), "错卦": cuo_gua(up, down),
        "动爻": p, "体": ti, "用": yong,
    }


def meihua(mode="time_shaoyong", year=None, month=None, day=None, hour=None,
           minute=0, numbers=None, xin=None, rand=False,
           number=None, digits=None, chars=None, guayao=None):
    now = datetime.datetime.now()
    # 报数 / 指定 / 随机等数字类起卦法：起念时辰折算为数，参与动爻（变爻）计算
    shi_h = hour if hour is not None else now.hour
    snum_shi = hour_to_shi(shi_h)
    if mode == "random" or rand:
        a = random.randint(1, 99)
        b = random.randint(1, 99)
        up, down, dong = mod8(a), mod8(b), mod6(a + b + snum_shi)
        method = "随机法"
        calc_detail = "%d·%d·%s(数%d)" % (a, b, shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    elif mode == "time_modern":
        hh = hour if hour is not None else now.hour
        mm = minute if minute is not None else now.minute
        up, down, dong = mod8(hh), mod8(mm), mod6(hh + mm)
        method = "现代时间起卦"
        calc_detail = "时%d·分%d" % (hh, mm)
        y, mo, d, h, mi = (year or now.year), (month or now.month), (day or now.day), hh, mm
    elif mode == "time_shaoyong":
        ynum, mnum, dnum, snum = time_to_yue_ri_shi(year, month, day, hour)
        s1 = ynum + mnum + dnum
        s = s1 + snum
        up, down, dong = mod8(s1), mod8(s), mod6(s)
        method = "邵雍古法时间起卦"
        calc_detail = "年支序%d·月%d·日%d·时%d" % (ynum, mnum, dnum, snum)
        y, mo, d, h, mi = year, month, day, hour, minute
    elif mode == "lifetime":
        # 终身起卦：用出生年月日时，规则同邵雍古法（时辰数已含在总和中）
        ynum, mnum, dnum, snum = time_to_yue_ri_shi(year, month, day, hour)
        s1 = ynum + mnum + dnum
        s = s1 + snum
        up, down, dong = mod8(s1), mod8(s), mod6(s)
        method = "终身起卦（出生农历 年%d 月%d 日%d·%s）" % (ynum, mnum, dnum, shi_name(snum))
        calc_detail = "年支序%d·月%d·日%d·时%d" % (ynum, mnum, dnum, snum)
        y, mo, d, h, mi = year, month, day, hour, minute
    elif mode == "single":
        # 单数起卦：一数加时成卦
        n = int(number)
        up = mod8(n)
        down = mod8(n + snum_shi)
        dong = mod6(n + snum_shi)
        method = "单数起卦"
        calc_detail = "%d·%s(数%d)" % (n, shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    elif mode == "three":
        # 三数起卦：上=A 下=B 动=(A+B+C+时辰数)%6
        a, b, c = int(numbers[0]), int(numbers[1]), int(numbers[2])
        up, down = mod8(a), mod8(b)
        dong = mod6(a + b + c + snum_shi)
        method = "三数起卦"
        calc_detail = "%d·%d·%d·%s(数%d)" % (a, b, c, shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    elif mode == "number11":
        # 数字起卦（3-16 位连续数字，11 位拆 6+5）：前段各位和为上卦、后段各位和为下卦
        s = str(digits)
        half = 6 if len(s) == 11 else (len(s) // 2)
        front, back = s[:half], s[half:]
        fsum = sum(int(c) for c in front)
        bsum = sum(int(c) for c in back)
        up, down = mod8(fsum), mod8(bsum)
        dong = mod6(fsum + bsum + snum_shi)
        method = "数字起卦（%d 位：%s｜%s）" % (len(s), front, back)
        calc_detail = "前段和%d·后段和%d·%s(数%d)" % (fsum, bsum, shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    elif mode == "hanzi":
        # 汉字起卦（2-4 字笔画）：2/3字 上=第1字 下=第2字；4字 上=前两字和 下=后两字和
        cs = "".join(str(chars).split())
        if not (2 <= len(cs) <= 4):
            raise ValueError("汉字起卦需 2-4 个汉字，收到 %d 个" % len(cs))
        st = hanzi_strokes_list(cs)
        if len(cs) == 4:
            up, down = mod8(st[0] + st[1]), mod8(st[2] + st[3])
        else:
            up, down = mod8(st[0]), mod8(st[1])
        dong = mod6(sum(st) + snum_shi)
        method = "汉字起卦（" + "、".join("%s%d画" % (c, n) for c, n in zip(cs, st)) + "）"
        calc_detail = "笔画和%d·%s(数%d)" % (sum(st), shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    elif mode == "guayao":
        # 指定起卦：直接指定上卦数、下卦数、动爻数（不取余、不加时辰）
        up, down, dong = int(guayao[0]), int(guayao[1]), int(guayao[2])
        if not (1 <= up <= 8 and 1 <= down <= 8 and 1 <= dong <= 6):
            raise ValueError("上/下卦数须在 1-8，动爻数须在 1-6")
        method = "指定起卦（上%s 下%s 动第 %d 爻）" % (XIANTIAN[up], XIANTIAN[down], dong)
        calc_detail = "上%d·下%d·动%d" % (up, down, dong)
        y, mo, d, h, mi = now.year, now.month, now.day, now.hour, now.minute
    else:  # baoshu / zhiding
        a, b = numbers[0], numbers[1]
        up, down, dong = mod8(a), mod8(b), mod6(a + b + snum_shi)
        if mode == "zhiding":
            method = "指定法"
            calc_detail = "%d·%d·%s(数%d)" % (a, b, shi_name(snum_shi), snum_shi)
        else:  # baoshu
            method = "报数法" + ("（%s心法）" % xin if xin else "")
            calc_detail = "%d·%d·%s(数%d)" % (a, b, shi_name(snum_shi), snum_shi)
        y, mo, d, h, mi = now.year, now.month, now.day, shi_h, now.minute
    greg, lunar_str, ganzhi, xunkong = compute_time_info(y, mo, d, h, mi)
    g = build_gua(up, down, dong)
    def pair_str(pair):
        return "%s（上%s下%s）" % (GUA_NAME[pair], XIANTIAN[pair[0]], XIANTIAN[pair[1]])
    return {
        "公历": greg,
        "阴历": lunar_str,
        "四柱": ganzhi,
        "旬空": xunkong,
        "起卦": method,
        "取数": calc_detail,
        "动爻": g["动爻"],
        "本卦": pair_str(g["本卦"]),
        "变卦": pair_str(g["变卦"]),
        "互卦": pair_str(g["互卦"]),
        "综卦": pair_str(g["综卦"]),
        "错卦": pair_str(g["错卦"]),
        "_raw": g,  # 内部保留，用于渲染卦画
    }


def format_text_plain(r):
    """纯文字版"""
    lines = [
        "【梅花易数起卦】",
        "",
        "起卦时间",
        "  公历：" + r["公历"],
        "  阴历：" + r["阴历"],
        "  四柱：" + r["四柱"],
        "  旬空：" + r["旬空"],
        "  起卦：" + r["起卦"],
        "  取数：" + r["取数"],
        "  动爻：第 %d 爻" % r["动爻"],
        "",
        "本卦：" + r["本卦"],
        "变卦：" + r["变卦"],
        "互卦：" + r["互卦"],
        "综卦：" + r["综卦"],
        "错卦：" + r["错卦"],
        "",
        "（本结果为规则推演参考，最终洞察请结合处境或咨询真人大师）",
    ]
    return "\n".join(lines)


def format_text(r):
    """图文版：顶部卦画 + 下方文字信息"""
    raw = r.get("_raw", {})
    pic = render_panel(raw) if raw else ""
    info = [
        "",
        "起卦时间",
        "  公历：" + r["公历"],
        "  阴历：" + r["阴历"],
        "  四柱：" + r["四柱"],
        "  旬空：" + r["旬空"],
        "  起卦：" + r["起卦"],
        "  取数：" + r["取数"],
        "  动爻：第 %d 爻" % r["动爻"],
        "",
        "（本结果为规则推演参考，最终洞察请结合处境或咨询真人大师）",
    ]
    return "【梅花易数起卦】\n" + pic + "\n" + "\n".join(info)


def main():
    ap = argparse.ArgumentParser(description="梅花易数起卦")
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--day", type=int)
    ap.add_argument("--hour", type=int, default=None,
                    help="小时(0-23)：时间法为起卦时刻；报数/随机/指定法为「起念小时」，"
                         "用于动爻的时辰数折算；缺省取运行当下时辰")
    ap.add_argument("--minute", type=int, default=0)
    ap.add_argument("--numbers", nargs=2, type=int, metavar=("A", "B"),
                    help="报数法（兼容旧写法），等同于 --baoshu")
    ap.add_argument("--baoshu", nargs=2, type=int, metavar=("A", "B"),
                    help="报数法：用户所报两数 A、B")
    ap.add_argument("--xin", choices=["随性", "灵性"], help="报数法心法：随性/灵性")
    ap.add_argument("--zhiding", nargs="+", type=int, metavar="N",
                    help="指定法：用户指定数字（手机号等单个数会自动拆两半；也可直接给 A B 两数）")
    ap.add_argument("--modern", action="store_true",
                    help="时间法·现代时间：时→上卦、分→下卦")
    ap.add_argument("--random", action="store_true", help="随机法")
    ap.add_argument("--lifetime", action="store_true",
                    help="终身起卦：--year --month --day --hour 填出生时间")
    ap.add_argument("--single", type=int, metavar="N", help="单数起卦：一个数 N")
    ap.add_argument("--three", nargs=3, type=int, metavar=("A", "B", "C"),
                    help="三数起卦：三个数 A B C")
    ap.add_argument("--digits", type=str, metavar="S",
                    help="数字起卦：3-16 位连续数字（11 位拆 6+5）")
    ap.add_argument("--chars", type=str, metavar="汉字",
                    help="汉字起卦：2-4 个汉字（按笔画数）")
    ap.add_argument("--guayao", nargs=3, type=int, metavar=("UP", "DOWN", "DONG"),
                    help="指定起卦：上卦数(1-8) 下卦数(1-8) 动爻数(1-6)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--text-only", action="store_true", help="仅输出纯文字，不显示卦画")
    ap.add_argument("--image", type=str, metavar="PATH", help="生成 PNG 图片到指定路径（如 output.png）")
    args = ap.parse_args()

    hh = args.hour if args.hour is not None else datetime.datetime.now().hour

    if args.random:
        r = meihua(mode="random", hour=hh)
    elif args.guayao:
        r = meihua(mode="guayao", guayao=args.guayao)
    elif args.chars:
        r = meihua(mode="hanzi", chars=args.chars, hour=hh)
    elif args.digits:
        r = meihua(mode="number11", digits=args.digits, hour=hh)
    elif args.single is not None:
        r = meihua(mode="single", number=args.single, hour=hh)
    elif args.three:
        r = meihua(mode="three", numbers=list(args.three), hour=hh)
    elif args.lifetime:
        if not (args.year and args.month and args.day):
            ap.error("终身起卦需提供 --year --month --day（--hour 出生时辰）")
        r = meihua(mode="lifetime", year=args.year, month=args.month,
                   day=args.day, hour=hh, minute=args.minute)
    elif args.modern:
        r = meihua(mode="time_modern", year=args.year, month=args.month,
                   day=args.day, hour=hh, minute=args.minute)
    elif args.zhiding:
        nums = list(args.zhiding)
        if len(nums) == 1:
            nums = split_long_number(nums[0])
        else:
            nums = nums[:2]
        r = meihua(mode="zhiding", numbers=nums, hour=hh)
    elif args.baoshu:
        r = meihua(mode="baoshu", numbers=list(args.baoshu), xin=args.xin, hour=hh)
    elif args.numbers:
        r = meihua(mode="baoshu", numbers=list(args.numbers), xin=args.xin, hour=hh)
    else:
        if not (args.year and args.month and args.day):
            ap.error("需提供 --year --month --day（时间邵雍古法/--lifetime 终身起卦），或 --modern，"
                     "或 --baoshu/--numbers A B（报数），或 --zhiding N（指定），或 --single N，"
                     "或 --three A B C，或 --digits S，或 --chars 汉字，或 --guayao UP DOWN DONG，或 --random")
        r = meihua(mode="time_shaoyong", year=args.year, month=args.month,
                   day=args.day, hour=hh, minute=args.minute)
    if args.image:
        out = render_image(r, args.image)
        print("[图片已保存] %s" % out)
        print()
        print(format_text(r))
    elif args.json:
        import json
        r2 = dict(r)
        r2.pop("_raw", None)
        print(json.dumps(r2, ensure_ascii=False, indent=2))
    elif args.text_only:
        print(format_text_plain(r))
    else:
        print(format_text(r))


if __name__ == "__main__":
    main()
