# -*- coding: utf-8 -*-
"""
解析全部附件 -> data/attach_blocks.json  {article_id: [blocks...]}
修复版：现场sniff文件类型，不依赖文件名扩展和旧kind字段
"""
import json, os, re

import xlrd
import docx as docxlib
import fitz  # PyMuPDF

d = json.load(open('data/attach_map.json', encoding='utf-8'))
attach = d['attach']
extracted = d.get('extracted', {})

out = {}

def add_block(pid, blk):
    out.setdefault(str(pid), []).append(blk)

def add_h(pid, title):
    add_block(pid, {'t': 'h3', 'x': title})

def img_block(path, cap=None):
    return {'t': 'img', 'src': path.replace('\\', '/'), 'cap': cap or ''}

def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def safe_cell(v):
    if v is None:
        return ''
    if isinstance(v, float) and abs(v - int(v)) < 1e-9:
        return str(int(v))
    s = str(v).strip()
    return s

def sniff(path):
    with open(path, 'rb') as f:
        head = f.read(16)
    if head.startswith(b'PK\x03\x04'):
        return 'docx'
    if head.startswith(b'Rar!\x1a\x07'):
        return 'rar'
    if head.startswith(b'\xd0\xcf\x11\xe0'):
        return 'ole'
    if head.startswith(b'%PDF'):
        return 'pdf'
    return 'bin'

def parse_xls(path):
    wb = xlrd.open_workbook(path, formatting_info=True)   # 必须：否则 merged_cells 为空
    blocks = []
    for si in range(wb.nsheets):
        sh = wb.sheet_by_index(si)
        if sh.nrows == 0:
            continue
        nrows = min(sh.nrows, 500)
        ncols = min(sh.ncols, 20)
        rows = []
        row_map = {}   # 原始行号 -> 清理后行号
        for r in range(nrows):
            row = []
            for c in range(ncols):
                try:
                    row.append(safe_cell(sh.cell_value(r, c)))
                except Exception:
                    row.append('')
            if any(x.strip() for x in row):
                row_map[r] = len(rows)
                rows.append(row)
        if not rows:
            continue
        # 合并单元格（映射到清理后的行号）：xlrd merged_cells = (rlo, rhi, clo, chi)
        merges = []
        try:
            for (rlo, rhi, clo, chi) in sh.merged_cells:
                if rlo not in row_map:
                    continue
                nr1 = row_map[rlo]
                nr2 = row_map.get(min(rhi, nrows) - 1, nr1)
                if clo >= ncols:
                    continue
                merges.append([nr1, clo, max(nr2, nr1), min(chi, ncols) - 1])
        except Exception:
            pass
        # 斜线表头判定：左上区域大合并 + 第二行第一列含"资质"（配备表特征）
        diag = any(m[0] == 0 and m[1] == 0 and m[2] >= 1 for m in merges) and \
            any('资质' in r[0] for r in rows[1:3] if r)
        blk = {'t': 'table', 'rows': rows, 'merges': merges}
        if diag:
            blk['diag'] = True
        if wb.nsheets > 1:
            blocks.append({'t': 'p', 'runs': [{'x': f'【工作表：{sh.name}】', 'b': True}]})
        blocks.append(blk)
    return blocks

def parse_docx(path, media_dir=None):
    """不访问style（规避cython兼容bug），返回 (blocks, media_imgs)"""
    blocks = []
    doc = docxlib.Document(path)
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            p = Paragraph(child, doc)
            txt = p.text.strip()
            if txt:
                blocks.append({'t': 'p', 'runs': [{'x': txt, 'b': False}]})
        elif tag == 'tbl':
            t = Table(child, doc)
            rows = []
            for row in t.rows:
                try:
                    cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
                except Exception:
                    cells = [''] * len(row.cells)
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append({'t': 'table', 'rows': rows})
    media_imgs = []
    if media_dir and os.path.isdir(media_dir):
        for fn in sorted(os.listdir(media_dir), key=natural_key):
            if re.search(r'\.(png|jpe?g|gif|bmp)$', fn, re.I):
                media_imgs.append(os.path.join(media_dir, fn))
    return blocks, media_imgs

def parse_pdf_to_imgs(path, out_prefix, zoom=2.0):
    docpdf = fitz.open(path)
    paths = []
    for i, page in enumerate(docpdf):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        fp = f'{out_prefix}_p{i+1:02d}.png'
        pix.save(fp)
        paths.append(fp)
    docpdf.close()
    return paths

# 行业划分表序号→行业名（建市[2007]86号附件1，经原图核实）
IND_NAMES = {1: '煤炭', 2: '化工石化医药', 3: '石油天然气', 4: '电力', 5: '冶金', 6: '军工', 7: '机械',
             8: '商物粮', 9: '核工业', 10: '电子通信广电', 11: '轻纺', 12: '建材', 13: '铁道', 14: '公路',
             15: '水运', 16: '民航', 17: '市政', 18: '农林', 19: '水利', 20: '海洋', 21: '建筑'}

def rar_img_cap(fname, series):
    """2-N.gif→配备表(行业名)；3-N→规模划分表；4-N→对照表"""
    m = re.match(r'(\d+)-(\d+)', os.path.basename(fname))
    if not m:
        return ''
    pre, n = int(m.group(1)), int(m.group(2))
    name = IND_NAMES.get(n, f'行业{n}')
    if series == 2:
        return f'【{name}行业】主要专业技术人员配备表'
    if series == 3:
        return f'【{name}行业】建设项目设计规模划分表'
    if series == 4:
        return f'【{name}行业】配备注册人员的专业设置对照表'
    return ''

# ================= 主循环 =================
stats = {'xls': 0, 'docx': 0, 'pdf': 0, 'doc_fail': 0, 'rar_imgs': 0, 'skip_dup': 0}
doc_fail_list = []
processed_files = set()

for pid_s, info in attach.items():
    pid = int(pid_s)
    for i, it in enumerate(info['items'], 1):
        p = it.get('file')
        if not p or not os.path.exists(p) or os.path.getsize(p) == 0:
            continue
        name = re.sub(r'(&gt;)+|点击打开|打开|&nbsp;', '', it['name']).strip() or f'附件{i}'
        kind = sniff(p)

        if kind == 'rar':
            prods = extracted.get(p, [])
            imgs = [q for q in prods if re.search(r'\.(gif|jpe?g|png)$', q, re.I)]
            imgs.sort(key=natural_key)
            if imgs:
                add_h(pid, f'附件：{name}（共{len(imgs)}张附表图片，按原编号排列）')
                for q in imgs:
                    base = os.path.basename(q)
                    series = None
                    m = re.match(r'(\d+)-', base)
                    if m:
                        series = int(m.group(1))
                    add_block(pid, img_block(q, cap=rar_img_cap(base, series)))
                stats['rar_imgs'] += len(imgs)
            continue

        key = os.path.realpath(p)
        if key in processed_files:
            stats['skip_dup'] += 1
            continue
        processed_files.add(key)

        if kind == 'docx':
            try:
                blocks, media_imgs = parse_docx(p, p + '_x/word/media' if os.path.isdir(p + '_x') else None)
                add_h(pid, f'附件：{name}（文件版全文）')
                out[str(pid)].extend(blocks)
                if media_imgs:
                    add_block(pid, {'t': 'p', 'runs': [{'x': '（文件内附图）', 'b': True}]})
                    for q in media_imgs:
                        add_block(pid, img_block(q))
                stats['docx'] += 1
            except Exception as e:
                print(f'docx解析失败 {p}: {type(e).__name__} {e}')
                doc_fail_list.append((pid, p, name))
            continue

        if kind == 'pdf':
            if pid == 100:
                imgs = parse_pdf_to_imgs(p, 'assets/attach/att100_pdf')
                add_h(pid, f'附件：{name}（原件共{len(imgs)}页）')
                for q in imgs:
                    add_block(pid, img_block(q))
                stats['pdf'] += 1
            elif pid in (101, 102, 103):
                add_h(pid, '附件：公路养护作业单位资质管理办法（中华人民共和国交通运输部令2021年第22号）')
                add_block(pid, {'t': 'p', 'runs': [{'x': '附件PDF原件全文已收录于本卷《公路养护作业单位资质管理办法》篇（见该篇附件原件页图），内容与本篇正文一致，不再重复收录。', 'b': False}]})
            elif pid == 6:
                imgs = parse_pdf_to_imgs(p, 'assets/attach/att6_pdf')
                add_h(pid, f'附件：建筑业企业资质管理规定（图片版PDF，共{len(imgs)}页）')
                for q in imgs:
                    add_block(pid, img_block(q))
                stats['pdf'] += 1
            continue

        if kind == 'ole':
            # 先试 xls
            try:
                blocks = parse_xls(p)
                if blocks:
                    add_h(pid, f'附件：{name}')
                    out[str(pid)].extend(blocks)
                    stats['xls'] += 1
                    continue
            except Exception:
                pass
            # 再试 docx（伪装doc）
            try:
                blocks, media_imgs = parse_docx(p, None)
                add_h(pid, f'附件：{name}（文件版全文）')
                out[str(pid)].extend(blocks)
                stats['docx'] += 1
                continue
            except Exception:
                pass
            print(f'.doc 需转换: {p} | {name}')
            doc_fail_list.append((pid, p, name))
            stats['doc_fail'] += 1
            continue

print('统计:', stats)
if doc_fail_list:
    print('待转换 .doc:')
    for pid, p, name in doc_fail_list:
        print(f'  id={pid} {p} {name[:40]}')

json.dump(out, open('data/attach_blocks.json', 'w', encoding='utf-8'), ensure_ascii=False)

for pid_s in sorted(out, key=lambda x: int(x)):
    n_tbl = sum(1 for b in out[pid_s] if b['t'] == 'table')
    n_img = sum(1 for b in out[pid_s] if b['t'] == 'img')
    n_txt = sum(1 for b in out[pid_s] if b['t'] in ('p', 'h4', 'h3'))
    print(f'id={pid_s}: 表格{n_tbl} 图片{n_img} 文本{n_txt}')
