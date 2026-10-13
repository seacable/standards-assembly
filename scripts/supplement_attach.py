# -*- coding: utf-8 -*-
"""补充解析剩余附件 -> 合并 attach_blocks.json -> 合并进 articles.json"""
import json, os, re, shutil
from docx_raw import parse_docx_raw, extract_media

out = json.load(open('data/attach_blocks.json', encoding='utf-8'))

def add_block(pid, blk):
    out.setdefault(str(pid), []).append(blk)

def add_h(pid, title):
    add_block(pid, {'t': 'h3', 'x': title})

def img_block(path, cap=''):
    return {'t': 'img', 'src': path.replace('\\', '/'), 'cap': cap}

# ---------- 1) id=24 官方行业划分表 GIF ----------
if os.path.exists('assets/attach/design86_hangye.pdf'):
    os.replace('assets/attach/design86_hangye.pdf', 'assets/attach/design86_hangye.gif')
add_h(24, '附件：工程设计行业划分表（建市〔2007〕86号官方附件，21个行业）')
add_block(24, img_block('assets/attach/design86_hangye.gif'))
print('id=24 行业划分表 GIF 已加入')

# ---------- 2) id=94 勘察9号文附件（官方红头文件页图） ----------
P = 'assets/attach/kc2013_pages'
add_h(94, '附件1：工程勘察行业主要专业技术人员配备表（建市〔2013〕9号官方文件页）')
add_block(94, img_block(f'{P}/p12.png'))
add_h(94, '附件2：工程勘察主要技术装备配备表（官方文件页，共3页）')
for n in (13, 14, 15):
    add_block(94, img_block(f'{P}/p{n}.png'))
add_h(94, '附件3：工程勘察项目规模划分表（官方文件页，共5页）')
for n in (16, 17, 18, 19, 20):
    add_block(94, img_block(f'{P}/p{n}.png'))
print('id=94 勘察附件1/2/3 已加入')

# ---------- 3) docx型附件（标题+整页截图） ----------
DOCX_ITEMS = [
    (6,   'assets/attach/att_6_1.docx',   '附件：建筑业企业资质管理规定（文件版，正文为整页扫描图）'),
    (92,  'assets/attach/att_92_1docx',   '附件：工程监理企业资质管理规定（文件版，正文为整页扫描图）'),
    (104, 'assets/attach/att_104_2docx',  '附件：房地产开发企业资质管理规定（文件版，正文为整页扫描图）'),
]
for pid, path, title in DOCX_ITEMS:
    blocks, imgs = parse_docx_raw(path)
    media_dir = path + '_media'
    saved = extract_media(path, media_dir)
    add_h(pid, title)
    out[str(pid)].extend(blocks)   # 标题段落
    for q in sorted(saved):
        add_block(pid, img_block(q))
    print(f'id={pid} docx附件已加入: 段落{len(blocks)} 图{len(saved)}')

# ---------- 4) 合并进 articles.json ----------
data = json.load(open('data/articles.json', encoding='utf-8'))
n_merge = 0
for c in data['categories']:
    for a in c['articles']:
        key = str(a['id'])
        if key in out and out[key]:
            # 去掉此前可能已合并的附件节（幂等）：截断到第一个附件节标题之前
            for idx, b in enumerate(a['blocks']):
                if b.get('t') == 'h3' and str(b.get('x', '')).startswith('附件'):
                    a['blocks'] = a['blocks'][:idx]
                    break
            a['blocks'].extend(out[key])
            n_merge += 1
print(f'合并完成: {n_merge} 篇文章追加了附件内容')
json.dump(data, open('data/articles.json', 'w', encoding='utf-8'), ensure_ascii=False)

# 汇总
for pid_s in sorted(out, key=lambda x: int(x)):
    n_tbl = sum(1 for b in out[pid_s] if b['t'] == 'table')
    n_img = sum(1 for b in out[pid_s] if b['t'] == 'img')
    print(f'  id={pid_s}: 附件表格{n_tbl} 附件图片{n_img}')
