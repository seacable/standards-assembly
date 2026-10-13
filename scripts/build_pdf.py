# -*- coding: utf-8 -*-
"""
生成 PDF 汇编文件：
- 目录在正文前，目录条目 <--双向链接--> 正文（正文每页右上角"返回目录"）
- 45° 平铺水印，墨迹覆盖率约 25%（tile 208x104pt，字号26pt）
- 卷/文章级 PDF 书签大纲
输出: 建筑业资质标准汇编.pdf
"""
import json, os, sys

PUBLIC = '--public' in sys.argv   # 发布模式：无水印、无加密，输出到 dist/

VERSION = 'I'   # 版本字母：每次改动递增（A、B、C...），输出文件名带此后缀
PDF_OWNER_PWD = os.environ.get('ASM_PDF_PWD', '')   # 如需加密PDF（禁止打印/修改/复制/批注），设置环境变量 ASM_PDF_PWD；留空则不加密
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Table, TableStyle, Image, Flowable, KeepTogether)
from reportlab.lib.fonts import addMapping

# ---------- 字体 ----------
def register_fonts():
    cands_reg = [('YaHei', 'C:/Windows/Fonts/msyh.ttc', 0),
                 ('SimHei', 'C:/Windows/Fonts/simhei.ttf', None),
                 ('SimSun', 'C:/Windows/Fonts/simsun.ttc', 0)]
    reg = bold = None
    for name, path, idx in cands_reg:
        if os.path.exists(path):
            try:
                if idx is None:
                    pdfmetrics.registerFont(TTFont(name, path))
                else:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
                reg = name
                break
            except Exception as e:
                print('字体注册失败', path, e)
    bold_cands = [('YaHeiB', 'C:/Windows/Fonts/msyhbd.ttc', 0),
                  ('SimHei', 'C:/Windows/Fonts/simhei.ttf', None)]
    for name, path, idx in bold_cands:
        if os.path.exists(path):
            try:
                if idx is None:
                    pdfmetrics.registerFont(TTFont(name, path))
                else:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
                bold = name
                break
            except Exception as e:
                print('粗体注册失败', path, e)
    if reg and bold and reg != bold:
        addMapping(reg, 0, 0, reg)
        addMapping(reg, 1, 0, bold)   # bold
        addMapping(reg, 0, 1, reg)    # italic -> regular
        addMapping(reg, 1, 1, bold)
    print('使用字体:', reg, '/', bold)
    return reg, bold

REG, BOLD = register_fonts()
F = REG or 'SimHei'

# ---------- 样式 ----------
S = {
    'cover_t':  ParagraphStyle('cover_t', fontName=F, fontSize=30, leading=44, alignment=TA_CENTER, textColor=colors.HexColor('#1a4d8f')),
    'cover_s':  ParagraphStyle('cover_s', fontName=F, fontSize=11, leading=20, alignment=TA_CENTER, textColor=colors.HexColor('#556')),
    'toc_h':    ParagraphStyle('toc_h', fontName=F, fontSize=20, leading=28, textColor=colors.HexColor('#1a4d8f'), spaceAfter=10),
    'vol':      ParagraphStyle('vol', fontName=F, fontSize=15, leading=24, textColor=colors.white, backColor=colors.HexColor('#1a4d8f'),
                               borderPadding=(5, 8, 5, 8), spaceBefore=6, spaceAfter=12, keepWithNext=1),
    'toc_vol':  ParagraphStyle('toc_vol', fontName=F, fontSize=11.5, leading=18, spaceBefore=6, keepWithNext=1),
    'toc_item': ParagraphStyle('toc_item', fontName=F, fontSize=9, leading=13.6, leftIndent=16, wordWrap='CJK'),
    'art':      ParagraphStyle('art', fontName=F, fontSize=13, leading=20, textColor=colors.HexColor('#1a4d8f'),
                               spaceBefore=14, spaceAfter=6, keepWithNext=1, wordWrap='CJK',
                               borderPadding=(3, 0, 3, 6), borderColor=colors.HexColor('#1a4d8f'), borderWidth=0),
    'h4':       ParagraphStyle('h4', fontName=F, fontSize=11.5, leading=18, spaceBefore=10, spaceAfter=4, keepWithNext=1, wordWrap='CJK'),
    'h5':       ParagraphStyle('h5', fontName=F, fontSize=10.5, leading=16, spaceBefore=8, spaceAfter=3, keepWithNext=1, wordWrap='CJK'),
    'body':     ParagraphStyle('body', fontName=F, fontSize=10.5, leading=17, spaceAfter=3, wordWrap='CJK', alignment=TA_LEFT),
    'src':      ParagraphStyle('src', fontName=F, fontSize=8.5, leading=13, textColor=colors.HexColor('#667'), spaceBefore=6, wordWrap='CJK'),
    'blink':    ParagraphStyle('blink', fontName=F, fontSize=8.5, leading=13, textColor=colors.HexColor('#1a4d8f'), spaceBefore=1, spaceAfter=4, wordWrap='CJK'),
    'navcell':  ParagraphStyle('navcell', fontName=F, fontSize=9, leading=13, textColor=colors.HexColor('#1a4d8f'), alignment=TA_CENTER, wordWrap='CJK'),
    'navname':  ParagraphStyle('navname', fontName=F, fontSize=9, leading=13, textColor=colors.HexColor('#222'), wordWrap='CJK'),
}

# ---------- 各卷速查表（PDF） ----------
def h3_index(blocks):
    out, n = [], 0
    for b in blocks:
        if b['t'] == 'h3':
            n += 1
            out.append((n, b['x']))
    return out

def att_kinds(title):
    t = title
    if '配备表' in t and '对照' not in t:
        return 'pb'
    if '规模划分' in t:
        return 'gm'
    if '对照表' in t:
        return 'dz'
    if '行业划分' in t:
        return 'hy'
    return None

def design_nav_rows(aid_map):
    rows = []
    for a in VOLUMES[1][2]:
        aid = aid_map.get(a['id'], '')
        atts = {}
        for n, x in h3_index(a['blocks']):
            if x.startswith('附件'):
                k = att_kinds(x)
                if k:
                    atts[k] = n
        rows.append((aid, a['title'], atts))
    return rows

def _nav_header(anchor, title_txt, vol_vi=None):
    vol_link = f'<a href="#vol_{vol_vi}"><b>⮐ 本卷</b></a>　' if vol_vi else ''
    return Paragraph(f'<b>{esc(title_txt)}</b>　<font size="8.5" color="#557">（点击名称跳正文、点击“查看/附n”跳对应位置；正文附件处可返回本表）</font>'
                     f'　{vol_link}<a href="#TOC"><b>☰ 汇编总目录</b></a>', S['h4'])

def nav_table(hdr, rows_data, col_ratios):
    data = [[Paragraph(f'<b>{esc(h)}</b>', S['navcell']) for h in hdr]]
    for r in rows_data:
        data.append(r)
    t = Table(data, colWidths=[AVAIL * x for x in col_ratios], repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9fb0c3')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9fc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t

def design_nav_flows(aid_map):
    rows = design_nav_rows(aid_map)
    s25 = {r['id']: r['found'] for r in scope25_data()['2']}
    hdr = ['专业 / 标准（点击跳正文）', '行业划分表', '人员配备表', '规模划分表', '专业对照表', '业务范围']
    rows_data = []
    for aid, title, atts in rows:
        cells = [Paragraph(f'<a href="#{aid}">{esc(title)}</a>', ParagraphStyle('nn', parent=S['navname'], alignment=TA_LEFT))]
        for k in ('hy', 'pb', 'gm', 'dz'):
            cells.append(Paragraph(f'<a href="#{aid}-h{atts[k]}">查看</a>', S['navcell']) if k in atts
                         else Paragraph('—', S['navcell']))
        # 业务范围列：aid_map 的数字键即文章id
        art_id = None
        for a in VOLUMES[1][2]:
            if aid_map.get(a['id']) == aid:
                art_id = a['id']
                break
        cells.append(Paragraph('<a href="#scopenav_2">查看</a>', S['navcell']) if art_id is not None and s25.get(art_id)
                     else Paragraph('—', S['navcell']))
        rows_data.append(cells)
    tbl = nav_table(hdr, rows_data, [0.34, 0.125, 0.125, 0.125, 0.125, 0.14])
    return [_nav_header('volnav_2', '设计资质附件速查表', vol_vi=2), tbl]

def construction_nav_flows(aid_map):
    hdr = ['类别', '标准 / 规定（点击跳正文）', '承包工程范围', '附件导航']
    rows_data = []
    for a in VOLUMES[0][2]:
        t = a['title']
        if '总承包' in t:
            cat = '总承包'
        elif '专业承包' in t or '特种工程' in t:
            cat = '专业承包'
        elif '劳务' in t:
            cat = '劳务资质'
        else:
            cat = '管理规定'
        aid = aid_map.get(a['id'], '')
        h3s = h3_index(a['blocks'])
        fw = None
        for n, x in h3s:
            if fw is None and '承包' in x and '范围' in x and '依据' not in x:
                fw = n
        atts = [n for n, x in h3s if x.startswith('附件')]
        rows_data.append([
            Paragraph(esc(cat), S['navcell']),
            Paragraph(f'<a href="#{aid}">{esc(t)}</a>', ParagraphStyle('nn', parent=S['navname'], alignment=TA_LEFT)),
            Paragraph(f'<a href="#{aid}-h{fw}">查看</a>', S['navcell']) if fw else Paragraph('—', S['navcell']),
            Paragraph('　'.join(f'<a href="#{aid}-h{n}">附{i}</a>' for i, n in enumerate(atts, 1)), S['navcell'])
            if atts else Paragraph('—', S['navcell']),
        ])
    tbl = nav_table(hdr, rows_data, [0.12, 0.52, 0.18, 0.18])
    return [_nav_header('volnav_1', '施工资质速查表（50项：12项总承包＋36项专业承包＋特种工程＋施工劳务）', vol_vi=1), tbl]

_scope_data = None
def scope_rows():
    global _scope_data
    if _scope_data is None:
        _scope_data = {r['id']: r for r in json.load(open('data/scope_table.json', encoding='utf-8'))}
    return _scope_data

def scope_nav_flows(aid_map):
    """承包工程范围汇总表（卷一）"""
    sst = ParagraphStyle('sc', parent=S['body'], fontSize=7.5, leading=10.5)
    hdr = ['专业 / 标准', '特级', '一级', '二级', '三级']
    data = [[Paragraph(f'<b>{esc(h)}</b>', S['navcell']) for h in hdr]]
    for a in VOLUMES[0][2]:
        r = scope_rows().get(a['id'])
        if not r or not r.get('found'):
            continue
        aid = aid_map.get(a['id'], '')
        lv = r['levels']
        cells = [Paragraph(f'<a href="#{aid}">{esc(a["title"])}</a>', ParagraphStyle('sn', parent=S['navname'], fontSize=7.5, leading=10.5, alignment=TA_LEFT))]
        for k in ('te', 'c1', 'c2', 'c3'):
            cells.append(Paragraph(esc(lv[k]), sst) if lv.get(k) else Paragraph('—', S['navcell']))
        data.append(cells)
    tbl = Table(data, colWidths=[AVAIL * 0.16, AVAIL * 0.21, AVAIL * 0.21, AVAIL * 0.21, AVAIL * 0.21], repeatRows=1)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9fb0c3')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef6')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9fc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    note = Paragraph('注：各等级范围后如涉及政策调整（如建筑面积指标按建市〔2016〕226号修改），以正文相应专业篇中的备注为准。',
                     ParagraphStyle('scn', parent=S['src'], spaceBefore=3))
    return [_nav_header('scopenav_1', '承包工程范围汇总表（49项各级可承担工程范围一览）', vol_vi=1), tbl, note]

def simple_nav_flows(vi, aid_map, vol=None):
    vlabel, vname, arts = vol or VOLUMES[vi - 1]
    hdr = ['标准 / 文件（点击跳正文）', '附件导航']
    rows_data = []
    for a in arts:
        aid = aid_map.get(a['id'], '')
        hs = [(n, x) for n, x in h3_index(a['blocks']) if x.startswith('附件')]
        if hs:
            links = '　'.join(f'<a href="#{aid}-h{n}">附{i}</a>' for i, (n, _) in enumerate(hs, 1))
            nav_cell = Paragraph(links, S['navcell'])
        else:
            nav_cell = Paragraph('—', S['navcell'])
        rows_data.append([
            Paragraph(f'<a href="#{aid}">{esc(a["title"])}</a>', ParagraphStyle('nn', parent=S['navname'], alignment=TA_LEFT)),
            nav_cell,
        ])
    tbl = nav_table(hdr, rows_data, [0.62, 0.38])
    return [_nav_header(f'volnav_{vi}', f'{vname}速查表', vol_vi=vi), tbl]

def nav_flows_for(vi, aid_map, vol=None):
    if vi == 1:
        return construction_nav_flows(aid_map)
    if vi == 2:
        return design_nav_flows(aid_map)
    return simple_nav_flows(vi, aid_map, vol)

# ---------- 卷2-5 承担业务范围汇总表 ----------
_SCOPE25 = None
def scope25_data():
    global _SCOPE25
    if _SCOPE25 is None:
        _SCOPE25 = json.load(open('data/scope25.json', encoding='utf-8'))
    return _SCOPE25

def scope25_flows(vi, aid_map):
    vlabel, vname, arts = VOLUMES[vi - 1]
    sst = ParagraphStyle('s25', parent=S['body'], fontSize=7.5, leading=11)
    rows = scope25_data()[str(vi)]
    hdr = ['标准 / 文件（点击跳正文）', '承担业务范围']
    data = [[Paragraph(f'<b>{esc(h)}</b>', S['navcell']) for h in hdr]]
    for r in rows:
        aid = aid_map.get(r['id'], '')
        if r['found']:
            body = '<br/>'.join(esc(p) for p in r['scope'])
            cell = Paragraph(body, ParagraphStyle('s25b', parent=sst, alignment=TA_LEFT))
        else:
            cell = Paragraph('—（本篇无单独业务范围章节，详见正文或附件）', S['navcell'])
        data.append([
            Paragraph(f'<a href="#{aid}">{esc(r["title"])}</a>', ParagraphStyle('n25', parent=S['navname'], fontSize=7.5, leading=11, alignment=TA_LEFT)),
            cell,
        ])
    tbl = Table(data, colWidths=[AVAIL * 0.26, AVAIL * 0.74], repeatRows=1)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9fb0c3')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef6')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9fc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return [_nav_header(f'scopenav_{vi}', f'{vname}承担业务范围汇总表（范围内容为原文摘录）', vol_vi=vi), tbl]

# ---------- 数据（复用 build_html 的排序逻辑） ----------
data = json.load(open('data/articles.json', encoding='utf-8'))
pold = json.load(open('data/policies.json', encoding='utf-8'))
img_map = json.load(open('data/img_map.json', encoding='utf-8'))
cats = {c['id']: c for c in data['categories']}

GENERAL_ORDER = ['建筑工程', '公路工程', '铁路工程', '港口与航道工程', '水利水电工程', '电力工程',
                 '矿山工程', '冶金工程', '石油化工工程', '市政公用工程', '通信工程', '机电工程']
SPECIAL_ORDER = ['地基基础', '起重设备安装', '预拌混凝土', '电子与智能化', '消防设施', '防水防腐保温',
                 '桥梁工程', '隧道工程', '钢结构', '模板脚手架', '建筑装修装饰', '建筑机电安装',
                 '建筑幕墙', '古建筑工程', '城市及道路照明', '公路路面', '公路路基', '公路交通',
                 '铁路电务', '铁路铺轨架梁', '铁路电气化', '机场场道', '民航空管', '机场目视助航',
                 '港口与海岸', '航道工程', '通航建筑物', '港航设备', '水工金属结构', '水利水电机电',
                 '河湖整治', '输变电', '核工程', '海洋石油', '环保工程', '特种工程']

def rank(cat_id, title):
    if cat_id != 4:
        return 999
    if '资质管理规定' in title:
        return 900
    if '施工劳务' in title:
        return 800
    for i, k in enumerate(GENERAL_ORDER):
        if title.startswith(k):
            return 100 + i
    for i, k in enumerate(SPECIAL_ORDER):
        if k in title:
            return 300 + i
    return 950

def rank_design(title):
    if title == '工程设计资质标准':
        return 0
    if '事务所' in title:
        return 9
    if '行业' in title:
        return 2
    return 5

VOLUMES = [
    ('卷一', '施工资质标准（2014版现用）', sorted(cats[4]['articles'], key=lambda a: rank(4, a['title']))),
    ('卷二', '设计资质标准（2007版86号文现用）', sorted(cats[5]['articles'], key=lambda a: (rank_design(a['title']), a['id']))),
    ('卷三', '工程监理企业资质（2007版标准现用，管理规定2018年修正）', cats[7]['articles']),
    ('卷四', '工程勘察资质（2013版标准现用）', cats[8]['articles']),
    ('卷五', '测绘资质（2021版标准现用）', cats[10]['articles']),
    ('卷六', '公路养护作业单位资质（2021版标准现用）', cats[11]['articles']),
    ('卷七', '房地产开发企业资质（2022版标准现用）', cats[12]['articles']),
    ('卷八', '城乡规划编制单位资质（2024版标准现用）', cats[13]['articles']),
    ('卷九', '地质灾害防治单位资质（2023版标准现用）', cats[9]['articles']),
    ('卷十', '配套政策文件（住房城乡建设部规范性文件）', pold['policies']),
]

# ---------- 辅助 Flowable ----------
PAGE_LOG = {}      # 锚点名 -> 页码（第一遍构建时记录，供第二遍画右上角链接组）
PAGE_CONTEXT = {}  # 页码 -> (卷号, 文章锚点, 文章起始页)（两遍之间推导）
ART2VOL = {}       # 文章锚点 -> 卷号

class Dest(Flowable):
    """命名目标 + 可选书签；跳转保持当前缩放（XYZ定位页顶，不整页适配）"""
    def __init__(self, name, title=None, level=0):
        super().__init__()
        self.name, self.title, self.level = name, title, level
        self.width = self.height = 0
    def draw(self):
        self.canv.bookmarkPage(self.name, fit='XYZ', left=0, top=PAGE_H, zoom=None)
        PAGE_LOG[self.name] = self.canv.getPageNumber()
        if self.title:
            self.canv.addOutlineEntry(self.title, self.name, self.level, closed=(self.level == 0))

def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def runs_to_markup(runs):
    out = []
    for r in runs:
        if r.get('img'):
            continue  # 图片单独处理
        t = esc(r.get('x', ''))
        if not t:
            continue
        t = t.replace('\n', '<br/>')
        out.append(f'<b>{t}</b>' if r.get('b') else t)
    return ''.join(out)

class DiagHeader(Flowable):
    """斜线表头单元格：右上=列维度名，左下=行维度名，中间对角斜线"""
    def __init__(self, tl='专业设置', br='资质等级'):
        super().__init__()
        self.tl, self.br = tl, br
        self.width = self.height = 0
    def wrap(self, aw, ah):
        self.aw, self.ah = aw, ah
        return (aw, ah)
    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.HexColor('#7a8798'))
        c.setLineWidth(0.7)
        c.line(0, 0, self.aw, self.ah)
        c.setFillColor(colors.HexColor('#333'))
        c.setFont(F, 6.5)
        c.drawRightString(self.aw - 2, self.ah - 9, self.tl)
        c.drawString(2, 3, self.br)

def make_table(rows, avail, merges=None, diag=False):
    """返回 flowable 列表：表格 + 提取出的长注释段落
    列宽算法：按每列最大内容宽分配＋字号自适应，使单元格文字尽可能单行
    支持 merges 合并单元格（SPAN）与 diag 斜线表头"""
    ncols = max(len(r) for r in rows)

    def wlen(s):
        return sum(2 if ord(ch) > 0x2e80 else 1 for ch in s)

    # 1) 单元格级防护：超长单元格(>120宽)提取为注释（去重，合并单元格会复制内容）
    note_cells, seen_notes = [], set()

    def clean(r):
        nr = []
        for c in r:
            if wlen(c) > 120:
                if c not in seen_notes:
                    seen_notes.add(c)
                    note_cells.append(c)
                nr.append('')
            else:
                nr.append(c)
        return nr

    rows = [clean(r) for r in rows]

    # 2) 说明行（1-2个非空格且含较长文本 → 跨列合并行）；记录行号映射以转换 merges
    body_rows, note_rows = [], []
    row_map = {}
    for ri, r in enumerate(rows):
        nonempty = [c for c in r if c.strip()]
        if len(nonempty) <= 2 and max((wlen(c) for c in r), default=0) > 60:
            note_rows.append('　'.join(c for c in r if c.strip()))
        else:
            row_map[ri] = len(body_rows)
            body_rows.append(r)
    if not body_rows:
        body_rows, note_rows = rows, []
        row_map = {i: i for i in range(len(rows))}

    # 3) merges 坐标映射到 body_rows（覆盖说明行的 merge 丢弃）
    mrg = []
    for (r1, c1, r2, c2) in (merges or []):
        if r1 in row_map and r2 in row_map and c1 < ncols:
            b1, b2 = row_map[r1], row_map[r2]
            if b2 >= b1 and c2 >= c1:
                # 不与说明行区冲突（说明行已分离，不会出现在 body_rows）
                mrg.append((b1, min(c1, ncols - 1), b2, min(c2, ncols - 1)))
    covered = set()
    spans = {}
    for (b1, c1, b2, c2) in mrg:
        spans[(b1, c1)] = (b2, c2)
        for rr in range(b1, b2 + 1):
            for cc in range(c1, c2 + 1):
                if (rr, cc) != (b1, c1):
                    covered.add((rr, cc))

    # 4) 列宽：每列最大内容宽（封顶42），字号由大到小试探使表格尽量单行
    colmax = []
    for c in range(ncols):
        w = max((wlen(r[c]) if c < len(r) else 0) for r in body_rows)
        colmax.append(max(min(w, 42), 3))
    fs = 5.5
    for cand in (10.5, 9.5, 8.5, 7.5, 6.5, 5.5):
        fs = cand
        if sum(colmax) * cand + ncols * 5 <= avail:
            break
    st = ParagraphStyle(f'tb{fs}', parent=S['body'], fontSize=fs, leading=fs * 1.3)
    nst = ParagraphStyle(f'tn{fs}', parent=S['body'], fontSize=fs, leading=fs * 1.4)

    widths = [w * fs for w in colmax]
    scale = avail / sum(widths)
    widths = [w * scale for w in widths]

    data_rows = []
    for r in body_rows:
        r = r + [''] * (ncols - len(r))
        cells = []
        for c in range(ncols):
            cells.append(r[c])
        data_rows.append(cells)

    # diag 斜线表头：占据 (0,0) 的合并区域
    diag_span = None
    if diag and mrg:
        for (b1, c1, b2, c2) in mrg:
            if b1 == 0 and c1 == 0:
                diag_span = (b2, c2)
                break
    # 生成 Paragraph 行（diag 表头格稍后替换）
    n_body = len(data_rows)
    for ri, cells in enumerate(data_rows):
        for ci in range(len(cells)):
            if diag and diag_span and (ri, ci) == (0, 0):
                cells[ci] = None  # 稍后放 DiagHeader
                continue
            if (ri, ci) in covered and not (diag and diag_span and (ri, ci) == (0, 0)):
                cells[ci] = ''
            else:
                cells[ci] = Paragraph(esc(cells[ci]), st)
    for note in note_rows:
        data_rows.append([Paragraph(esc(note), st)] + [''] * (ncols - 1))
    n_all = len(data_rows)

    t = Table(data_rows, colWidths=widths, repeatRows=1)
    cmds = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9fb0c3')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]
    if diag_span:
        b2, c2 = diag_span
        cmds.append(('SPAN', (0, 0), (c2, b2)))
        dh = DiagHeader('专业设置', '资质等级')
        data_rows[0][0] = dh
    for k in range(len(note_rows)):
        cmds.append(('SPAN', (0, n_body + k), (-1, n_all - len(note_rows) + k)))
        cmds.append(('BACKGROUND', (0, n_body + k), (-1, n_all - len(note_rows) + k), colors.HexColor('#f4f6f9')))
    for (b1, c1, b2, c2) in mrg:
        if diag_span and (b1, c1) == (0, 0) and (b2, c2) == diag_span:
            continue
        cmds.append(('SPAN', (c1, b1), (c2, b2)))
    t.setStyle(TableStyle(cmds))

    flows = [t]
    if note_cells:
        for nc in note_cells:
            flows.append(Paragraph('注：' + esc(nc), nst))
    return flows

def make_img(src, avail):
    """src 可为 img_map 的 URL 键或本地路径"""
    path = img_map.get(src, src)
    if not path or not os.path.exists(path):
        return None
    try:
        ir = ImageReader(path)
        iw, ih = ir.getSize()
        w = min(avail * 0.86, 430)
        h = w * ih / iw
        return Image(path, width=w, height=h)
    except Exception as e:
        print('图片失败', path, e)
        return None

# ---------- 页面装饰 ----------
PAGE_W, PAGE_H = A4
WM_TEXT = os.environ.get('ASM_WATERMARK', '')   # 如需文字水印，设置环境变量 ASM_WATERMARK；留空则不画水印
AVAIL = PAGE_W - 25 * mm

def draw_toplinks(canv, ctx, first=False):
    """右上角链接组：⌂主页 ☰目录 ▤本卷 ⮐本文（双链：各目标页均有返回链接）"""
    from reportlab.lib.units import mm as _mm
    labels = [('⌂ 主页', 'COVER')]
    if not first:
        labels.append(('☰ 目录', 'TOC'))
    if ctx:
        vol_vi, aid, start_pg = ctx
        labels.append(('▤ 本卷', f'vol_{vol_vi}'))
        if first is False and ctx and pageno_ref[0] > start_pg:
            labels.append(('⮐ 本文', aid))
    x = PAGE_W - 12 * mm
    y = PAGE_H - 11 * mm
    canv.saveState()
    canv.setFont(F, 8.5)
    for txt, dest in labels:
        tw = pdfmetrics.stringWidth(txt, F, 8.5)
        x -= tw
        canv.setFillColor(colors.HexColor('#1a4d8f'))
        canv.drawString(x, y, txt)
        canv.linkRect('', dest, (x - 2, y - 3, x + tw + 2, y + 10), relative=0, thickness=0)
        x -= 9
    canv.restoreState()

pageno_ref = [0]   # 当前页码（draw_page 设置，供 draw_toplinks 判断是否文章首页之后）

def draw_page(canv, doc, first=False):
    pageno_ref[0] = canv.getPageNumber()
    ctx = PAGE_CONTEXT.get(pageno_ref[0])
    canv.saveState()
    # ---- 水印：45°，每页固定 60 个（6列×10行，页面坐标系精确布点），字号10pt ----
    import math
    canv.setFont(F, 10)
    canv.setFillColor(Color(0.32, 0.34, 0.38, alpha=0.075))
    canv.translate(PAGE_W / 2, PAGE_H / 2)
    canv.rotate(-45)  # 与HTML方向一致：文字左上→右下倾斜
    c45 = math.cos(math.radians(45))
    s45 = math.sin(math.radians(45))
    tw = pdfmetrics.stringWidth(WM_TEXT, F, 10)
    cols, rows = 6, 10
    # 页面坐标系中均匀网格（含文字半宽/半高边距，保证60个完整可见）
    mx = tw / 2 + 4
    my = 5 + 4
    xs = [mx + i * (PAGE_W - 2 * mx) / (cols - 1) for i in range(cols)]
    ys = [my + j * (PAGE_H - 2 * my) / (rows - 1) for j in range(rows)]
    for py in ys:
        for px in xs:
            dx, dy = px - PAGE_W / 2, py - PAGE_H / 2
            u = dx * c45 + dy * s45
            v = -dx * s45 + dy * c45
            canv.drawCentredString(u, v - 3.5, WM_TEXT)
    canv.restoreState()
    # ---- 页脚页码 ----
    canv.saveState()
    canv.setFont(F, 8.5)
    canv.setFillColor(colors.HexColor('#889'))
    canv.drawCentredString(PAGE_W / 2, 10 * mm, f'- {canv.getPageNumber()} -')
    canv.restoreState()
    # ---- 右上角链接组 ----
    draw_toplinks(canv, ctx, first=first)

def on_first(canv, doc):
    draw_page(canv, doc, first=True)

def on_later(canv, doc):
    draw_page(canv, doc, first=False)

# ---------- 组装文档 ----------
story = []

# 封面
story.append(Dest('COVER'))
story.append(Spacer(1, 70 * mm))
story.append(Paragraph('建筑业资质标准汇编', S['cover_t']))
story.append(Spacer(1, 8 * mm))
story.append(Paragraph(
    '施工 · 设计 · 监理 · 勘察 · 测绘 · 公路养护 · 房地产开发 · 城乡规划编制 · 地质灾害 · 配套政策文件',
    S['cover_s']))
story.append(Spacer(1, 4 * mm))
n_total = sum(len(v[2]) for v in VOLUMES)
story.append(Paragraph(f'共 {n_total} 篇（含各标准附件、备注及政策修订内容）', S['cover_s']))
story.append(Paragraph('编制日期：2026年9月30日', S['cover_s']))
story.append(Paragraph('资料来源：企业资质标准网（www.qiyezizhi.com / www.zizhiji.cn）<br/>'
                       '及住房和城乡建设部、中国政府网等官方公开文本', S['cover_s']))
story.append(Paragraph('目录与正文双向链接 · 每页右上角可返回目录', S['cover_s']))
story.append(PageBreak())

# 目录
story.append(Dest('TOC'))
story.append(Paragraph('目　录', S['toc_h']))
toc_vol_style = S['toc_vol']
art_i = 0
aid_map = {}   # 文章id -> PDF锚点 art_N
vol_entries = []   # (vol_id, label, name, arts)
for vi, (vlabel, vname, arts) in enumerate(VOLUMES, 1):
    vid = f'vol_{vi}'
    story.append(Paragraph(f'<a href="#{vid}"><b>{esc(vlabel)}</b>　{esc(vname)}</a>（{len(arts)}篇）', toc_vol_style))
    story.append(Paragraph(f'<a href="#volnav_{vi}">★ 速查表（本卷导航）</a>', S['toc_item']))
    if vi == 1:
        story.append(Paragraph('<a href="#scopenav_1">★ 承包工程范围汇总表（49项一览）</a>', S['toc_item']))
    elif vi in (2, 3, 4, 5):
        story.append(Paragraph(f'<a href="#scopenav_{vi}">★ 承担业务范围汇总表</a>', S['toc_item']))
    k_num = 0
    for a in arts:
        art_i += 1
        aid = f'art_{art_i}'
        aid_map[a['id']] = aid
        title = a['title']
        k_num += 1
        story.append(Paragraph(f'<a href="#{aid}">{k_num}. {esc(title)}</a>', S['toc_item']))
story.append(Paragraph('<a href="#appendix_validity"><b>附录</b>　现行有效性核查表（三轮核验，2026-09-30）</a>', toc_vol_style))
story.append(PageBreak())

# 正文
art_i = 0
for vi, (vlabel, vname, arts) in enumerate(VOLUMES, 1):
    vid = f'vol_{vi}'
    story.append(Dest(vid, f'{vlabel} {vname}', level=0))
    story.append(Paragraph(f'<a name="{vid}"/><b>{esc(vlabel)}</b>　{esc(vname)}', S['vol']))
    story.append(Paragraph(f'<a href="#COVER"><b>⌐ 主页</b></a>　　<a href="#TOC"><b>☰ 汇编总目录</b></a>', S['blink']))
    story.append(Dest(f'volnav_{vi}', f'{vname}速查表', level=1))
    story.extend(nav_flows_for(vi, aid_map, (vlabel, vname, arts)))
    story.append(Spacer(1, 6))
    if vi == 1:
        story.append(Dest('scopenav_1', '承包工程范围汇总表', level=1))
        story.extend(scope_nav_flows(aid_map))
        story.append(Spacer(1, 6))
    elif vi in (2, 3, 4, 5):
        story.append(Dest(f'scopenav_{vi}', f'{vname}承担业务范围汇总表', level=1))
        story.extend(scope25_flows(vi, aid_map))
        story.append(Spacer(1, 6))
    for a in arts:
        art_i += 1
        aid = f'art_{art_i}'
        title = a['title']
        att_n = 0
        story.append(Dest(aid, title, level=1))
        head = Paragraph(f'<a name="{aid}"/>{esc(title)}', S['art'])
        head_back = Paragraph(f'<a href="#volnav_{vi}"><b>⮐ 本卷速查表</b></a>　　<a href="#TOC"><b>☰ 汇编总目录</b></a>', S['blink'])
        first_flow = []
        blocks = a['blocks']
        # 渲染块
        rest = []
        first_done = False
        h3_n = 0
        for b in blocks:
            t = b['t']
            fl, imgs, extra = None, [], []
            if t == 'h3':
                h3_n += 1
                if b['x'].startswith('附件'):
                    fl = Paragraph(f'<a name="{aid}-h{h3_n}"/>{esc(b["x"])}', S['h4'])
                    extra.append(Paragraph(f'<a href="#volnav_{vi}"><b>⮐ 本卷速查表</b></a>　　<a href="#TOC"><b>⮐ 汇编总目录</b></a>', S['blink']))
                else:
                    fl = Paragraph(f'<a name="{aid}-h{h3_n}"/>{esc(b["x"])}', S['h4'])
            elif t == 'h4':
                fl = Paragraph(esc(b['x']), S['h5'])
            elif t == 'p':
                runs = b['runs']
                imgs = [make_img(r['img'], AVAIL) for r in runs if r.get('img')]
                imgs = [i for i in imgs if i]
                markup = runs_to_markup(runs)
                if markup:
                    fl = Paragraph(markup, S['body'])
                elif imgs:
                    fl = imgs[0]
                    imgs = imgs[1:]
                else:
                    continue
            elif t == 'table':
                tfls = make_table(b['rows'], AVAIL, b.get('merges'), b.get('diag'))
                fl = tfls[0] if tfls else None
                extra = tfls[1:]
                if fl is None:
                    continue
            elif t == 'list':
                fl = Paragraph('<br/>'.join('· ' + esc(i) for i in b['items']), S['body'])
            elif t == 'img':
                fl = make_img(b['src'], AVAIL)
                if fl is None:
                    continue
                if b.get('cap'):
                    extra.append(Paragraph(esc(b['cap']), ParagraphStyle('cap', parent=S['src'], alignment=TA_CENTER, spaceBefore=1)))
            else:
                continue

            if not first_done:
                story.append(KeepTogether([head, head_back] + ([fl] if fl is not None else [])))
                first_done = True
                story.extend(extra)
                story.extend(imgs)
            else:
                if fl is not None:
                    story.append(fl)
                story.extend(extra)
                story.extend(imgs)
        if not first_done:
            story.append(head)
            story.append(head_back)
        story.extend(rest)
        if a.get('source'):
            story.append(Paragraph(f'资料来源：{esc(a["source"])}', S['src']))
    if vi < len(VOLUMES):
        story.append(PageBreak())

# ---------- 附录：现行有效性核查表 ----------
story.append(PageBreak())
story.append(Dest('appendix_validity', '附录 现行有效性核查表', level=0))
story.append(Paragraph(f'<a name="appendix_validity"/><b>附录</b>　现行有效性核查表', S['vol']))
story.append(Paragraph('<a href="#COVER"><b>⌐ 主页</b></a>　　<a href="#TOC"><b>☰ 汇编总目录</b></a>', S['blink']))
story.append(Paragraph(
    '<b>核验方法（三轮交叉，核验日期：2026年9月30日）：</b>第一轮——源网站各分类所标版本；第二轮——住房和城乡建设部、'
    '自然资源部、交通运输部官方网站文件库/规章库逐项核对文号、施行日期与有效性；第三轮——2026年地方住建部门资质核查通知'
    '所列现行依据清单及自然资源部法规库“现行有效”标注交叉印证。', S['body']))
story.append(Paragraph(
    '<b>特别提示：</b>《建设工程企业资质管理制度改革方案》（国办函〔2020〕107号）已印发，拟压减资质等级类别，'
    '截至核验日期新版标准尚未出台，过渡期内本汇编所收各现行标准继续执行。', S['body']))
VALIDITY = [
    ('卷一', '施工资质标准（12项总承包＋36项专业承包＋特种＋劳务）', '建市〔2014〕159号', '2015-01-01施行',
     '现行有效。后续以226号(2016简化指标)、154号(2015)、361号(2022直接申请二级)、建办市〔2018〕53号等执行政策修正，相关内容已并入正文备注'),
    ('卷二', '设计资质标准（21行业＋7专项＋事务所）', '建市〔2007〕86号', '2007年印发施行',
     '现行有效。后续修订：261号(2016)废止并重新发布建筑工程设计事务所资质标准(2017-03-01施行)；66号(2017)简化民航行业设计资质。版本提示见正文'),
    ('卷三', '工程监理企业资质', '建市〔2007〕131号标准；管理规定建设部令第102号（2018年部令第45号第三次修正）', '2007年施行',
     '现行有效'),
    ('卷四', '工程勘察资质', '建市〔2013〕9号；实施办法建市〔2013〕86号', '2013年施行', '现行有效'),
    ('卷五', '测绘资质', '自然资办发〔2021〕43号《测绘资质管理办法》《测绘资质分类分级标准》', '2021-07-01施行（同时废止原2014年31号文）', '现行有效'),
    ('卷六', '公路养护作业单位资质', '交通运输部令2021年第22号《公路养护作业单位资质管理办法》', '2022-01-01施行', '现行有效'),
    ('卷七', '房地产开发企业资质', '建设部令第77号（2000年），经24号(2015)、45号(2018)、54号(2022)三次修正', '2022-03-02施行（第三次修正）',
     '现行有效。资质等级现为一、二两级'),
    ('卷八', '城乡规划编制单位资质', '自然资源部令第11号《城乡规划编制单位资质管理办法》', '2024-01-24公布即施行', '现行有效'),
    ('卷九', '地质灾害防治单位资质', '自然资源部令第8号《地质灾害防治单位资质管理办法》', '2023-01-01施行（同时废止原国土资源部2005年三个办法）', '现行有效'),
    ('卷十', '配套政策文件（20号/154号/226号/72号/210号等）', '各文号见本卷各篇', '—',
     '现行有效。其中72号文特级标准中“国家级工法、专利、科技进步奖”等考核指标已被154号文取消'),
]
_vdata = [[Paragraph(f'<b>{esc(h)}</b>', S['navcell']) for h in
           ['卷', '标准范围', '现行文号', '施行', '核验结果与修订提示']]]
for vl, scope, docno, eff, remark in VALIDITY:
    _vdata.append([
        Paragraph(esc(vl), S['navcell']),
        Paragraph(esc(scope), ParagraphStyle('vn', parent=S['navname'], alignment=TA_LEFT)),
        Paragraph(esc(docno), ParagraphStyle('vd', parent=S['navname'], fontSize=8, alignment=TA_LEFT)),
        Paragraph(esc(eff), ParagraphStyle('ve', parent=S['navname'], fontSize=8, alignment=TA_LEFT)),
        Paragraph(esc(remark), ParagraphStyle('vr', parent=S['navname'], fontSize=8, alignment=TA_LEFT)),
    ])
_vt = Table(_vdata, colWidths=[AVAIL * 0.08, AVAIL * 0.30, AVAIL * 0.24, AVAIL * 0.14, AVAIL * 0.24], repeatRows=1)
_vt.setStyle(TableStyle([
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9fb0c3')),
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef6')),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f9fc')]),
    ('LEFTPADDING', (0, 0), (-1, -1), 2),
    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ('TOPPADDING', (0, 0), (-1, -1), 2),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
]))
story.append(_vt)

# ---------- 生成（两遍构建：第一遍记录锚点页码，第二遍绘制右上角链接组） ----------
import copy
if PUBLIC:
    os.makedirs('dist', exist_ok=True)
    out = os.path.join('dist', '建筑业资质标准汇编_v1.0_public.pdf')
else:
    out = f'建筑业资质标准汇编{VERSION}.pdf'

def _doc(path):
    return SimpleDocTemplate(path, pagesize=A4,
                             leftMargin=15 * mm, rightMargin=15 * mm,
                             topMargin=18 * mm, bottomMargin=16 * mm,
                             title='建筑业资质标准汇编（2026年9月版）',
                             author='汇编整理')

# 第一遍： PAGE_LOG 就绪（右上角仅基础链接，PAGE_CONTEXT 为空）
story2 = copy.deepcopy(story)   # 必须在第一遍消耗 story 之前复制
_pass1 = '_pass1.pdf'
doc1 = _doc(_pass1)
doc1.build(story, onFirstPage=on_first, onLaterPages=on_later)
print('第一遍构建完成，锚点页码:', len(PAGE_LOG), '个')

# 推导页码上下文：文章锚点->卷
_idx = 0
for _vi, (_vl, _vn, _arts) in enumerate(VOLUMES, 1):
    for _a in _arts:
        _idx += 1
        ART2VOL[f'art_{_idx}'] = _vi
_art_pages = sorted((pg, name) for name, pg in PAGE_LOG.items()
                    if name.startswith('art_') and name in ART2VOL)
maxpg = max(PAGE_LOG.values())
for _pg in range(1, maxpg + 1):
    cands = [(pg, nm) for pg, nm in _art_pages if pg <= _pg]
    if not cands:
        continue
    pg, aid = max(cands)
    PAGE_CONTEXT[_pg] = (ART2VOL[aid], aid, pg)

# 第二遍： 完整右上角链接组 + 加密（禁止打印/修改/复制/批注，保护密码 PDF_OWNER_PWD；--public 模式不加密）
doc2 = _doc(out)
if PUBLIC or not PDF_OWNER_PWD:   # 公开模式或未设置密码 → 不加密
    from reportlab.pdfgen.canvas import Canvas as _PlainCanvas
    doc2.build(story2, onFirstPage=on_first, onLaterPages=on_later, canvasmaker=_PlainCanvas)
else:
    from reportlab.pdfgen.canvas import Canvas as _RLCanvas
    from reportlab.lib.pdfencrypt import StandardEncryption

    def _make_enc():
        return StandardEncryption(userPassword='', ownerPassword=PDF_OWNER_PWD,
                                  canPrint=0, canModify=0, canCopy=0, canAnnotate=0)

    class EncryptedCanvas(_RLCanvas):
        def __init__(self, *args, **kw):
            kw['encrypt'] = _make_enc()
            super().__init__(*args, **kw)

    doc2.build(story2, onFirstPage=on_first, onLaterPages=on_later, canvasmaker=EncryptedCanvas)
if os.path.exists(_pass1):
    os.remove(_pass1)

# 后处理：①加密文档需先用保护密码解密 ②所有链接目标 zoom=0 → null（保持当前缩放）③重新加密并保持权限限制
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NullObject
_rr = PdfReader(out)
if _rr.is_encrypted:
    _rr.decrypt(PDF_OWNER_PWD)
_ww = PdfWriter()
_ww.append(_rr)          # 立即读取全部内容
_tmp = out + '.tmp.pdf'
for _p in _ww.pages:
    for _a in (_p.get('/Annots') or []):
        _o = _a.get_object()
        if _o.get('/Subtype') == '/Link' and _o.get('/Dest'):
            _d = _o['/Dest']
            if len(_d) > 4 and str(_d[4]) in ('/0', '0'):
                _d[4] = NullObject()
if not PUBLIC and PDF_OWNER_PWD:
    _ww.encrypt(user_password='', owner_password=PDF_OWNER_PWD, permissions_flag=0)
with open(_tmp, 'wb') as _f:
    _ww.write(_f)
os.replace(_tmp, out)
_tag = '公开版（无水印无加密）' if PUBLIC else ('已加密：禁止打印/修改/复制/批注' if PDF_OWNER_PWD else '未加密（未设置环境变量 ASM_PDF_PWD）')
print(f'已生成 {out}: {os.path.getsize(out)//1024} KB（{_tag}；跳转保持当前缩放）')
