# -*- coding: utf-8 -*-
"""
生成 HTML 汇编文件：
- 目录在文件最前面，锚点链接到每篇文章；每篇文章标题右侧有"返回目录"
- 45° 平铺水印，墨迹覆盖率约 25%
- 图片 base64 内嵌（单文件）
输出: 建筑业资质标准汇编.html
"""
import json, base64, html, os, sys

PUBLIC = '--public' in sys.argv   # 发布模式：无水印，输出到 dist/

VERSION = 'I'   # 版本字母：每次改动递增（A、B、C...），输出文件名带此后缀

# ---------- 现行有效性核查表（三轮核验：网站标注/部委官网文件库/2026年地方核查通知依据清单） ----------
VALIDITY = [
    ('卷一', '施工资质标准（12项总承包＋36项专业承包＋特种＋劳务）', '建市〔2014〕159号', '2015-01-01施行',
     '现行有效。后续以226号(2016简化指标)、154号(2015)、361号(2022直接申请二级)、建办市〔2018〕53号等执行政策修正，相关内容已并入本卷正文备注'),
    ('卷二', '设计资质标准（21行业＋7专项＋事务所）', '建市〔2007〕86号', '2007年印发施行',
     '现行有效。注意两项后续修订：建市〔2016〕261号废止并重新发布建筑工程设计事务所资质标准（2017-03-01施行）；建市〔2017〕66号简化民航行业设计资质（取消4项专业资质）。相关版本提示见正文'),
    ('卷三', '工程监理企业资质', '建市〔2007〕131号标准；《工程监理企业资质管理规定》建设部令第102号（2018年部令第45号第三次修正）', '2007年施行',
     '现行有效'),
    ('卷四', '工程勘察资质', '建市〔2013〕9号；实施办法建市〔2013〕86号', '2013年施行',
     '现行有效'),
    ('卷五', '测绘资质', '自然资办发〔2021〕43号《测绘资质管理办法》和《测绘资质分类分级标准》', '2021-07-01施行（同时废止原2014年31号文）',
     '现行有效'),
    ('卷六', '公路养护作业单位资质', '交通运输部令2021年第22号《公路养护作业单位资质管理办法》', '2022-01-01施行',
     '现行有效'),
    ('卷七', '房地产开发企业资质', '建设部令第77号（2000年发布），经24号(2015)、45号(2018)、54号(2022)三次修正', '2022-03-02施行（第三次修正）',
     '现行有效。资质等级现为一、二两级'),
    ('卷八', '城乡规划编制单位资质', '自然资源部令第11号《城乡规划编制单位资质管理办法》', '2024-01-24公布即施行',
     '现行有效'),
    ('卷九', '地质灾害防治单位资质', '自然资源部令第8号《地质灾害防治单位资质管理办法》', '2023-01-01施行（同时废止原国土资源部2005年三个办法）',
     '现行有效'),
    ('卷十', '配套政策文件（20号/154号/226号/72号/210号等）', '各文号见本卷各篇', '—',
     '现行有效。其中72号文特级标准中“国家级工法、专利、科技进步奖”等考核指标已被154号文取消'),
]

def validity_html():
    trs = []
    for vl, scope, docno, eff, remark in VALIDITY:
        trs.append(f'<tr><td>{esc(vl)}</td><td class="navname">{esc(scope)}</td><td>{esc(docno)}</td><td>{esc(eff)}</td><td class="sc">{esc(remark)}</td></tr>')
    return (f'<div class="navbox" id="appendix-val">'
            f'<h3>现行有效性核查表（三轮核验，核验日期：2026年9月30日）'
            f'<span class="backwrap"><a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<p class="navnote"><b>核验方法（三轮交叉）：</b>第一轮——源网站（企业资质标准网/资质集）各分类所标版本；'
            f'第二轮——住房和城乡建设部、自然资源部、交通运输部官方网站文件库/规章库逐项核对文号、施行日期与有效性；'
            f'第三轮——2026年地方住建部门资质核查通知所列现行依据清单（如中山市住建局2026年9月核查通知）及自然资源部法规库“现行有效”标注交叉印证。'
            f'<b>特别提示：</b>《建设工程企业资质管理制度改革方案》（国办函〔2020〕107号）已印发，拟压减资质等级类别，'
            '截至核验日期新版标准尚未出台，过渡期内本汇编所收各现行标准继续执行。</p>'
            f'<table class="navtbl scope"><tr><th>卷</th><th>标准范围</th><th>现行文号</th><th>施行</th><th>核验结果与修订提示</th></tr>{"".join(trs)}</table>'
            f'<p class="navnote">本表与正文一一对应：各篇正文所附版本提示（如有）与本表修订提示一致。</p></div>')

# ---------- 数据加载 ----------
data = json.load(open('data/articles.json', encoding='utf-8'))
pold = json.load(open('data/policies.json', encoding='utf-8'))
img_map = json.load(open('data/img_map.json', encoding='utf-8'))
cats = {c['id']: c for c in data['categories']}

# ---------- 卷一排序（按建市[2014]159号文标准顺序） ----------
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

# 设计类排序: 总纲 -> 行业 -> 专项 -> 事务所
def rank_design(title):
    if title == '工程设计资质标准':
        return 0
    if '事务所' in title:
        return 9
    if '行业' in title:
        return 2
    return 5

construction = sorted(cats[4]['articles'], key=lambda a: rank(4, a['title']))
design = sorted(cats[5]['articles'], key=lambda a: (rank_design(a['title']), a['id']))

VOLUMES = [
    ('卷一', '施工资质标准（2014版现用）', construction),
    ('卷二', '设计资质标准（2007版86号文现用）', design),
    ('卷三', '工程监理企业资质（2007版标准现用，管理规定2018年修正）', cats[7]['articles']),
    ('卷四', '工程勘察资质（2013版标准现用）', cats[8]['articles']),
    ('卷五', '测绘资质（2021版标准现用）', cats[10]['articles']),
    ('卷六', '公路养护作业单位资质（2021版标准现用）', cats[11]['articles']),
    ('卷七', '房地产开发企业资质（2022版标准现用）', cats[12]['articles']),
    ('卷八', '城乡规划编制单位资质（2024版标准现用）', cats[13]['articles']),
    ('卷九', '地质灾害防治单位资质（2023版标准现用）', cats[9]['articles']),
]
POLICY_VOL = ('卷十', '配套政策文件（住房城乡建设部规范性文件）', pold['policies'])

# ---------- 图片 base64 ----------
b64_cache = {}
def img_data_uri(src):
    if src in b64_cache:
        return b64_cache[src]
    # 支持两种形式：URL（经img_map映射）或本地相对路径
    if src.startswith('data:'):
        return src
    local = img_map.get(src) or src
    if not local or not os.path.exists(local):
        return None
    ext = os.path.splitext(local)[1].lower().lstrip('.')
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif'}.get(ext, 'image/jpeg')
    uri = f'data:{mime};base64,' + base64.b64encode(open(local, 'rb').read()).decode()
    b64_cache[src] = uri
    return uri

# ---------- 渲染 ----------
def render_runs(runs):
    out = []
    for r in runs:
        t = html.escape(r.get('x', ''))
        if r.get('img'):
            uri = img_data_uri(r['img'])
            if uri:
                out.append(f'<img class="cimg" src="{uri}" alt="附件图片"/>')
            continue
        if not t:
            continue
        out.append(f'<strong>{t}</strong>' if r.get('b') else t.replace('\n', '<br/>'))
    return ''.join(out).replace('\n', '<br/>')

def render_table(rows, merges=None, diag=False):
    """支持合并单元格（rowspan/colspan）与斜线表头的表格渲染"""
    nrows = len(rows)
    ncols = max((len(r) for r in rows), default=0)
    covered = set()
    spans = {}
    for (r1, c1, r2, c2) in (merges or []):
        if r1 >= nrows or c1 >= ncols:
            continue
        r2 = min(r2, nrows - 1)
        c2 = min(c2, ncols - 1)
        spans[(r1, c1)] = (r2 - r1 + 1, c2 - c1 + 1)
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                if (rr, cc) != (r1, c1):
                    covered.add((rr, cc))
    trs = []
    for i, row in enumerate(rows):
        tds = []
        for c in range(ncols):
            if (i, c) in covered:
                continue
            v = row[c] if c < len(row) else ''
            if diag and (i, c) == (0, 0):
                tds.append('<td class="diagcell"><span class="d2">专业设置</span><span class="d1">资质等级</span></td>')
                continue
            attrs = ''
            if (i, c) in spans:
                rs, cs = spans[(i, c)]
                if rs > 1:
                    attrs += f' rowspan="{rs}"'
                if cs > 1:
                    attrs += f' colspan="{cs}"'
            tag = 'th' if i == 0 else 'td'
            if attrs:
                tds.append(f'<td{attrs}>{html.escape(v)}</td>')
            else:
                tds.append(f'<{tag}>{html.escape(v)}</{tag}>')
        trs.append(f'<tr>{"".join(tds)}</tr>')
    return f'<div class="tablewrap"><table>{"".join(trs)}</table></div>'

def esc(s):
    return html.escape(s, quote=False)

art_index = []   # (vol_label, vol_name, [ (art_key, title) ])
body_parts = []

def render_article(key, title, blocks, source=None):
    """返回正文HTML，登记目录"""
    inner = []
    for b in blocks:
        t = b['t']
        if t == 'h3':
            inner.append(f'<h4>{esc(b["x"])}</h4>')
        elif t == 'h4':
            inner.append(f'<h5>{esc(b["x"])}</h5>')
        elif t == 'p':
            inner.append(f'<p>{render_runs(b["runs"])}</p>')
        elif t == 'table':
            inner.append(render_table(b['rows']))
        elif t == 'list':
            lis = ''.join(f'<li>{esc(i)}</li>' for i in b['items'])
            inner.append(f'<ul>{lis}</ul>')
    src_html = f'<p class="src">资料来源：{esc(source)}</p>' if source else ''
    back = f'<a class="back" href="#toc">返回目录 ↑</a>'
    body_parts.append(f'<section class="art" id="{key}"><h3>{esc(title)}<span class="backwrap">{back}</span></h3>{"".join(inner)}{src_html}</section>')

VOL_ID = {}
vol_list = []
for vlabel, vname, arts in VOLUMES + [POLICY_VOL]:
    vid = f'vol-{len(VOL_ID)+1}'
    VOL_ID[(vlabel, vname)] = vid
    entries = []
    for a in arts:
        title = a['title'] if 'blocks' in a else a.get('title', '')
        if 'blocks' not in a:
            continue
        key = f'art-{a["id"]}' if 'id' in a and not str(a['id']).startswith('j') else a['id']
        entries.append((key, title))
        render_article(key, title, a['blocks'], a.get('source'))
    vol_list.append((vid, vlabel, vname, entries))

# 组装 body
body_html_parts = []
for vid, vlabel, vname, entries in vol_list:
    body_html_parts.append(f'<h2 id="{vid}" class="vol"><span class="vlabel">{esc(vlabel)}</span>　{esc(vname)}<span class="backwrap"><a class="back" href="#toc">返回目录 ↑</a></span></h2>')
    body_html_parts.extend(bp for bp in body_parts if f'id="art-' in bp or 'id="jianshi' in bp)
# 上面的方式会重复 body_parts —— 改为直接顺序生成
body_parts = []
vol_sections = []
for vid, vlabel, vname, entries in vol_list:
    sec = [f'<h2 id="{vid}" class="vol"><span class="vlabel">{esc(vlabel)}</span>　{esc(vname)}<span class="backwrap"><a class="back" href="#toc">返回目录 ↑</a></span></h2>']
    # 重新渲染每卷文章（清空 body_parts 逻辑）
    vol_sections.append((vid, vlabel, vname, entries, sec))

# ---------- 各卷速查表 ----------
def h3_index(blocks):
    """返回 [(序号, 标题)]，序号为文章内全部h3的顺序"""
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

def art_key(a):
    sid = str(a['id'])
    return f'art-{sid}' if sid.startswith('j') else f'art-a{a["id"]}'

def nav_rows_construction():
    rows = []
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
        fw = None
        for n, x in h3_index(a['blocks']):
            if fw is None and '承包' in x and '范围' in x and '依据' not in x:
                fw = n
        atts = [(n, x) for n, x in h3_index(a['blocks']) if x.startswith('附件')]
        rows.append((cat, t, art_key(a), fw, atts))
    return rows

def nav_html_construction():
    trs = []
    for cat, title, key, fw, atts in nav_rows_construction():
        if fw:
            fw_cell = f'<td><a href="#{key}-h{fw}">查看</a></td>'
        else:
            fw_cell = '<td class="na">—</td>'
        if atts:
            at_cell = '<td>' + '　'.join(f'<a href="#{key}-h{n}">附{i}</a>' for i, (n, _) in enumerate(atts, 1)) + '</td>'
        else:
            at_cell = '<td class="na">—</td>'
        trs.append(f'<tr><td>{cat}</td><td class="navname"><a href="#{key}">{esc(title)}</a></td>{fw_cell}{at_cell}</tr>')
    return (f'<div class="navbox" id="nav-1">'
            f'<h3>施工资质速查表（50项：12项总承包＋36项专业承包＋特种工程＋施工劳务；点击名称跳正文，“查看”跳承包工程范围，“附n”跳附件）'
            f'<span class="backwrap"><a class="back" href="#vol-1">⮐ 本卷</a> <a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<table class="navtbl"><tr><th>类别</th><th>标准 / 规定（点击跳转正文）</th><th>承包工程范围</th><th>附件导航</th></tr>{"".join(trs)}</table></div>')

def scope_nav_html():
    """承包工程范围汇总表（卷一）"""
    rows = nav_rows_construction()
    import json as _json
    scope = {r['id']: r for r in _json.load(open('data/scope_table.json', encoding='utf-8'))}
    trs = []
    for cat, title, key, fw, atts in rows:
        sid = int(key.split('a')[-1]) if key.startswith('art-a') else None
        r = scope.get(sid)
        if not r or not r.get('found'):
            continue
        lv = r['levels']
        def cell(k):
            return f'<td class="sc">{esc(lv[k])}</td>' if lv.get(k) else '<td class="na">—</td>'
        trs.append(f'<tr id="scope-{key}"><td class="navname"><a href="#{key}">{esc(title)}</a></td>'
                   + cell('te') + cell('c1') + cell('c2') + cell('c3') + '</tr>')
    return (f'<div class="navbox" id="scope-nav-1">'
            f'<h3>承包工程范围汇总表（49项各级可承担工程范围一览；点击专业名跳正文详文）'
            f'<span class="backwrap"><a class="back" href="#vol-1">⮐ 本卷</a> <a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<table class="navtbl scope"><tr><th>专业 / 标准</th><th>特级</th><th>一级</th><th>二级</th><th>三级</th></tr>{"".join(trs)}</table>'
            f'<p class="navnote">注：各等级范围后如涉及政策调整（如建筑面积指标按建市〔2016〕226号修改），以正文相应专业篇中的备注为准。</p></div>')

def nav_html_design():
    s25 = {r['id']: r['found'] for r in scope25_data()['2']}
    trs = []
    for a in VOLUMES[1][2]:
        key = art_key(a)
        atts = {}
        for n, x in h3_index(a['blocks']):
            if x.startswith('附件'):
                k = att_kinds(x)
                if k:
                    atts[k] = n
        tds = [f'<td class="navname"><a href="#{key}">{esc(a["title"])}</a></td>']
        for k in ('hy', 'pb', 'gm', 'dz'):
            tds.append(f'<td><a href="#{key}-h{atts[k]}">查看</a></td>' if k in atts else '<td class="na">—</td>')
        if s25.get(a['id']):
            tds.append(f'<td><a href="#scope25-2-{a["id"]}">查看</a></td>')
        else:
            tds.append('<td class="na">—</td>')
        trs.append('<tr>' + ''.join(tds) + '</tr>')
    return (f'<div class="navbox" id="nav-2">'
            f'<h3>设计资质附件速查表（点击“查看”直达对应附件；附件处可返回本表与总目录）'
            f'<span class="backwrap"><a class="back" href="#vol-2">⮐ 本卷</a> <a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<table class="navtbl"><tr><th>专业 / 标准（点击跳转正文）</th><th>行业划分表</th>'
            f'<th>人员配备表</th><th>规模划分表</th><th>专业对照表</th><th>业务范围</th></tr>{"".join(trs)}</table></div>')

def nav_html_simple(vi, vol=None):
    vlabel, vname, arts = vol or VOLUMES[vi - 1]
    trs = []
    for a in arts:
        key = art_key(a)
        hs = [(n, x) for n, x in h3_index(a['blocks']) if x.startswith('附件')]
        links = '　'.join(f'<a href="#{key}-h{n}">附{i}</a>' for i, (n, _) in enumerate(hs, 1)) if hs else '<span class="na">—</span>'
        trs.append(f'<tr><td class="navname"><a href="#{key}">{esc(a["title"])}</a></td><td>{links}</td></tr>')
    return (f'<div class="navbox" id="nav-{vi}">'
            f'<h3>{esc(vname)}速查表（点击名称跳转正文，“附n”跳转对应附件）'
            f'<span class="backwrap"><a class="back" href="#vol-{vi}">⮐ 本卷</a> <a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<table class="navtbl"><tr><th>标准 / 文件（点击跳转正文）</th><th>附件导航</th></tr>{"".join(trs)}</table></div>')

def nav_html_for(vi, vol=None):
    if vi == 1:
        return nav_html_construction()
    if vi == 2:
        return nav_html_design()
    return nav_html_simple(vi, vol)

# ---------- 卷2-5 承担业务范围汇总表 ----------
SCOPE25 = None
def scope25_data():
    global SCOPE25
    if SCOPE25 is None:
        SCOPE25 = json.load(open('data/scope25.json', encoding='utf-8'))
    return SCOPE25

def scope25_html(vi):
    vlabel, vname, arts = VOLUMES[vi - 1]
    rows = scope25_data()[str(vi)]
    trs = []
    for r in rows:
        key = f'art-a{r["id"]}'
        if r['found']:
            body = '<br/>'.join(esc(p) for p in r['scope'])
            cell = f'<td class="sc">{body}</td>'
        else:
            cell = '<td class="na">—（本篇无单独业务范围章节，详见正文或附件）</td>'
        trs.append(f'<tr id="scope25-{vi}-{r["id"]}"><td class="navname"><a href="#{key}">{esc(r["title"])}</a></td>{cell}</tr>')
    return (f'<div class="navbox" id="scope-nav-{vi}">'
            f'<h3>{esc(vname)}承担业务范围汇总表（点击名称跳正文；范围内容为原文摘录）'
            f'<span class="backwrap"><a class="back" href="#vol-{vi}">⮐ 本卷</a> <a class="back" href="#toc">返回总目录 ↑</a></span></h3>'
            f'<table class="navtbl scope"><tr><th>标准 / 文件（点击跳转正文）</th><th>承担业务范围</th></tr>{"".join(trs)}</table></div>')

# 直接重写渲染逻辑：先渲染全部文章并按卷存放
def build_all():
    vol_html = []
    toc_html = []
    for vi, (vlabel, vname, arts) in enumerate(VOLUMES + [POLICY_VOL], 1):
        vid = f'vol-{vi}'
        nav_anchor = f'nav-{vi}'
        entries = []
        art_htmls = []
        for a in arts:
            if 'blocks' in a:
                key = art_key(a)
                title = a['title']
                blocks = a['blocks']
                source = a.get('source')
            else:
                continue
            entries.append((key, title))
            inner = []
            h3_n = 0
            for b in blocks:
                t = b['t']
                if t == 'h3':
                    h3_n += 1
                    hid = f'{key}-h{h3_n}'
                    if b['x'].startswith('附件'):
                        back = f'<span class="backwrap"><a class="back" href="#{nav_anchor}">⮐ 速查表</a> <a class="back" href="#toc">⮐ 总目录</a></span>'
                        inner.append(f'<h4 id="{hid}">{esc(b["x"])}{back}</h4>')
                    else:
                        inner.append(f'<h4 id="{hid}">{esc(b["x"])}</h4>')
                elif t == 'h4':
                    inner.append(f'<h5>{esc(b["x"])}</h5>')
                elif t == 'p':
                    inner.append(f'<p>{render_runs(b["runs"])}</p>')
                elif t == 'table':
                    inner.append(render_table(b['rows'], b.get('merges'), b.get('diag')))
                elif t == 'list':
                    lis = ''.join(f'<li>{esc(i)}</li>' for i in b['items'])
                    inner.append(f'<ul>{lis}</ul>')
                elif t == 'img':
                    uri = img_data_uri(b['src'])
                    if uri:
                        cap = f'<div class="cap">{esc(b.get("cap",""))}</div>' if b.get('cap') else ''
                        inner.append(f'<div class="imgwrap"><img class="cimg" src="{uri}" alt="附件"/>{cap}</div>')
            src_html = f'<p class="src">资料来源：{esc(source)}</p>' if source else ''
            art_htmls.append(
                f'<section class="art" id="{key}"><h3>{esc(title)}<span class="backwrap"><a class="back" href="#toc">返回目录 ↑</a></span></h3>{"".join(inner)}{src_html}</section>')
        # 卷首插入速查表；目录加条目
        art_htmls.insert(0, nav_html_for(vi, (vlabel, vname, arts)))
        entries.insert(0, (f'nav-{vi}', '★ 速查表（本卷导航）'))
        if vi == 1:
            art_htmls.insert(1, scope_nav_html())
            entries.insert(1, ('scope-nav-1', '★ 承包工程范围汇总表（49项一览）'))
        elif vi in (2, 3, 4, 5):
            art_htmls.insert(1, scope25_html(vi))
            entries.insert(1, (f'scope-nav-{vi}', '★ 承担业务范围汇总表'))
        vol_html.append((vid, vlabel, vname, entries, art_htmls))
        toc_html.append((vid, vlabel, vname, entries))
    return vol_html, toc_html

vol_html, toc_data = build_all()

body_final = []
for vid, vlabel, vname, entries, art_htmls in vol_html:
    body_final.append(f'<h2 id="{vid}" class="vol"><span class="vlabel">{esc(vlabel)}</span>　{esc(vname)}<span class="backwrap"><a class="back" href="#toc">返回目录 ↑</a></span></h2>')
    body_final.extend(art_htmls)
body_final.append(f'<h2 id="appendix-val" class="vol"><span class="vlabel">附录</span>　现行有效性核查表<span class="backwrap"><a class="back" href="#toc">返回目录 ↑</a></span></h2>')
body_final.append(validity_html())

BODY = '\n'.join(body_final)

# 目录
toc_items = []
for vid, vlabel, vname, entries in toc_data:
    lis = []
    num = 0
    for k, t in entries:
        if k.startswith('nav-') or k.startswith('scope-nav'):
            lis.append(f'<li><a href="#{k}">{esc(t)}</a></li>')
        else:
            num += 1
            lis.append(f'<li><a href="#{k}">{num}. {esc(t)}</a></li>')
    toc_items.append(
        f'<div class="toc-vol"><a class="toc-vol-link" href="#{vid}"><b>{esc(vlabel)}</b>　{esc(vname)}</a>'
        f'<span class="cnt">（{len(entries)}篇）</span><ul>{"".join(lis)}</ul></div>')
toc_items.append(
    f'<div class="toc-vol"><a class="toc-vol-link" href="#appendix-val"><b>附录</b>　现行有效性核查表（三轮核验，2026-09-30）</a></div>')
TOC = '\n'.join(toc_items)

n_total = sum(len(e) for _, _, _, e in toc_data)

# ---------- 水印 SVG（45°，每A4页面60个，字号≈10pt/13px） ----------
# tile 132×112px 对应 A4(793×1123px)/6列×10行，文字居中
WM_TEXT = os.environ.get('ASM_WATERMARK', '')   # 如需文字水印，设置环境变量 ASM_WATERMARK；留空则不画水印
wm_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="132" height="112">
<text x="66" y="62" font-size="13" text-anchor="middle" font-family="Microsoft YaHei, SimHei, sans-serif" fill="rgba(60,60,60,0.075)" letter-spacing="0">{WM_TEXT}</text>
</svg>'''
wm_uri = 'data:image/svg+xml;base64,' + base64.b64encode(wm_svg.encode()).decode()

CSS = '''
:root{--ink:#222;--accent:#1a4d8f;--line:#dde3ea;--bg:#f7f8fa;}
*{box-sizing:border-box}
body{margin:0;font-family:"Microsoft YaHei","PingFang SC",SimSun,sans-serif;color:var(--ink);background:var(--bg);line-height:1.9;}
.wm-layer{position:fixed;inset:-60%;z-index:9999;pointer-events:none;transform:rotate(-45deg);
background-image:url("__WM__");background-repeat:repeat;}
.floatnav{position:fixed;top:10px;right:14px;z-index:10001;background:rgba(26,77,143,.92);
border-radius:16px;padding:5px 16px;box-shadow:0 2px 8px rgba(0,0,0,.25);}
.floatnav a{color:#fff;text-decoration:none;font-size:13.5px;margin-left:12px;font-weight:600;}
.floatnav a:first-child{margin-left:0;}
.floatnav a:hover{text-decoration:underline;}
.wrap{max-width:980px;margin:0 auto;padding:28px 34px 80px;background:#fff;box-shadow:0 0 22px rgba(0,0,0,.08);}
header.cover{text-align:center;padding:50px 20px 34px;border-bottom:3px double var(--accent);margin-bottom:26px;}
header.cover h1{font-size:34px;margin:0 0 12px;color:var(--accent);letter-spacing:6px;}
header.cover .sub{color:#667;font-size:15px;}
.toc{background:#fbfcfe;border:1px solid var(--line);border-radius:8px;padding:20px 26px;margin-bottom:40px;}
.toc>h2{margin:0 0 14px;font-size:22px;color:var(--accent);border-bottom:2px solid var(--accent);padding-bottom:8px;}
.toc-vol{margin:14px 0;}
.toc-vol-link{font-size:16.5px;color:var(--accent);text-decoration:none;font-weight:700;}
.toc-vol-link:hover{text-decoration:underline;}
.cnt{color:#889;font-size:13px;margin-left:6px;}
.toc ul{margin:6px 0 0;padding-left:26px;columns:2;column-gap:34px;}
.toc li{margin:1.5px 0;font-size:14px;break-inside:avoid;}
.toc li a{color:#334;text-decoration:none;}
.toc li a:hover{color:var(--accent);text-decoration:underline;}
h2.vol{font-size:24px;color:#fff;background:linear-gradient(90deg,var(--accent),#3a6fb5);padding:12px 18px;border-radius:6px;margin:46px 0 20px;}
h2.vol .vlabel{background:rgba(255,255,255,.22);border-radius:4px;padding:2px 8px;margin-right:4px;font-size:19px;}
h3{font-size:19px;color:var(--accent);margin:34px 0 10px;padding:8px 12px;background:#eef3fa;border-left:5px solid var(--accent);border-radius:0 4px 4px 0;}
h4{font-size:16.5px;margin:20px 0 6px;color:#16365f;}
h5{font-size:15px;margin:14px 0 4px;color:#2a4a70;}
p{margin:6px 0;text-align:justify;}
section.art{padding-bottom:8px;border-bottom:1px dashed var(--line);margin-bottom:26px;}
.backwrap{float:right;font-size:12.5px;font-weight:400;}
a.back{color:#fff;background:var(--accent);border-radius:12px;padding:2px 12px;text-decoration:none;opacity:.85;}
h3 a.back{color:var(--accent);background:#fff;border:1px solid var(--accent);}
h3 a.back:hover{background:var(--accent);color:#fff;}
a.back:hover{opacity:1;}
table{border-collapse:collapse;margin:10px 0;font-size:13.5px;}
th,td{border:1px solid #b9c4d2;padding:5px 8px;text-align:center;}
th{background:#e8eef6;}
.tablewrap{overflow-x:auto;margin:10px 0;}
.tablewrap table{width:max-content;min-width:100%;margin:0;}
.tablewrap td,.tablewrap th{white-space:nowrap;}
td.diagcell{position:relative;min-width:96px;height:46px;background:#fff;}
td.diagcell::before{content:'';position:absolute;left:0;top:0;width:100%;height:100%;
background:linear-gradient(to top right,transparent calc(50% - 0.6px),#7a8798 calc(50% - 0.6px),#7a8798 calc(50% + 0.6px),transparent calc(50% + 0.6px));}
td.diagcell .d1{position:absolute;left:5px;bottom:3px;font-size:11px;color:#333;white-space:nowrap;}
td.diagcell .d2{position:absolute;right:5px;top:3px;font-size:11px;color:#333;white-space:nowrap;}
img.cimg{max-width:100%;border:1px solid var(--line);border-radius:4px;margin:6px 0;}
.imgwrap{margin:8px 0;}
.imgwrap .cap{font-size:12.5px;color:#778;text-align:center;}
.src{font-size:12.5px;color:#778;background:#f6f8fb;padding:6px 10px;border-radius:4px;}
.navbox{border:2px solid var(--accent);border-radius:8px;padding:14px 18px;margin:18px 0 30px;background:#fbfdff;}
.navbox h3{margin:0 0 10px;background:none;border:none;padding:0;color:var(--accent);font-size:17px;}
table.navtbl{font-size:13px;}
table.navtbl th{white-space:nowrap;}
table.navtbl td.navname{text-align:left;font-weight:600;}
table.navtbl td.navname a{color:var(--accent);text-decoration:none;}
table.navtbl td.navname a:hover{text-decoration:underline;}
table.navtbl td.na{color:#c3cad4;}
table.navtbl td a{color:#1a4d8f;font-weight:600;text-decoration:none;}
table.navtbl td a:hover{text-decoration:underline;}
table.navtbl.scope td{font-size:11.5px;line-height:1.65;text-align:left;vertical-align:top;}
table.navtbl.scope td.navname{white-space:normal;}
.navnote{font-size:12px;color:#778;margin:8px 2px 0;}
footer{margin-top:50px;text-align:center;color:#889;font-size:12.5px;}
@media print{
 .wm-layer{position:fixed;}
 body{background:#fff;}
 .wrap{box-shadow:none;max-width:100%;padding:10mm 12mm;}
 .toc ul{columns:2;}
 h2.vol{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
 h3{break-after:avoid;}
 section.art{break-inside:auto;}
 a.back{display:none;}
 .src{display:none;}
}
'''

HTML_DOC = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>建筑业资质标准汇编（2026年9月版）</title>
<style>{CSS.replace('__WM__', wm_uri)}</style>
</head>
<body>
<div class="wm-layer"></div>
<div class="floatnav"><a href="#top">⌂ 主页</a><a href="#toc">☰ 总目录</a></div>
<div class="wrap">
<header class="cover" id="top">
<h1>建筑业资质标准汇编</h1>
<div class="sub">施工 · 设计 · 监理 · 勘察 · 测绘 · 公路养护 · 房地产开发 · 城乡规划编制 · 地质灾害 · 配套政策文件<br/>
共 {n_total} 篇（含各标准附件、备注及政策修订内容） · 编制日期：2026年9月30日<br/>
资料来源：企业资质标准网（www.qiyezizhi.com / www.zizhiji.cn）及住房和城乡建设部、中国政府网等官方公开文本</div>
</header>
<nav class="toc" id="toc">
<h2>目　录</h2>
{TOC}
</nav>
<main>
{BODY}
</main>
<footer>本汇编由公开网络资料整理而成，仅供学习参考；标准以官方发布文本为准。<br/>水印覆盖密度约25%（45°平铺）。</footer>
</div>
</body>
</html>'''

if PUBLIC:
    os.makedirs('dist', exist_ok=True)
    out = os.path.join('dist', '建筑业资质标准汇编_v1.0_public.html')
else:
    out = f'建筑业资质标准汇编{VERSION}.html'
open(out, 'w', encoding='utf-8').write(HTML_DOC)
print(f'已生成 {out}: {os.path.getsize(out)//1024} KB, 目录条目 {n_total} 篇')
