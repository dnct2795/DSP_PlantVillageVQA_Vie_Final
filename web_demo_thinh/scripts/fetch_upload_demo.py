"""Tải 5 ảnh bệnh lá ngoài thực tế từ Wikimedia Commons (giấy phép mở) để người dùng tự upload khi demo.
Ghi samples/upload_demo/manifest.json (nguồn, tác giả, giấy phép, sha256, đáp án đúng = loài cây + bệnh)."""
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import certifi
from PIL import Image

os.environ['SSL_CERT_FILE'] = certifi.where()
UA = {'User-Agent': 'hoila-demo-sample-fetcher/0.1 (research demo; see repository)'}
API = 'https://commons.wikimedia.org/w/api.php'
OUT = Path(__file__).resolve().parents[1] / 'samples/upload_demo'
PICKS = [
    ('up01_khoai_tay_moc_suong.jpg', 'File:Late blight on potato leaf 2.jpg', 'khoai tây', 'bệnh mốc sương', 'Potato · late blight'),
    ('up02_bi_phan_trang.jpg', 'File:Kürbis-Cucurbita-Echter Mehltau-Golovinomyces-4-JS.jpg', 'bí', 'bệnh phấn trắng', 'Squash · powdery mildew'),
    ('up03_tao_gi_sat_tuyet_tung.jpg', 'File:Cedar apple rust on crab apple leaf upper surface.JPG', 'táo', 'bệnh gỉ sắt táo tuyết tùng', 'Apple · cedar apple rust'),
    ('up04_ngo_chay_la_lon.jpg', 'File:Northern corn leaf blight.JPG', 'ngô', 'bệnh cháy lá lớn', 'Corn · northern leaf blight'),
    ('up05_ca_chua_dom_la_septoria.jpg', 'File:Septoria leaf spot symptoms on tomato leaf (Septoria lycopersici on Solanum lycopersicum leaf).jpg', 'cà chua', 'bệnh đốm lá Septoria', 'Tomato · Septoria leaf spot'),
]


def api(params):
    url = API + '?' + urllib.parse.urlencode(dict(params, format='json'))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def strip_tags(s):
    out, skip = [], False
    for ch in s:
        if ch == '<': skip = True
        elif ch == '>': skip = False
        elif not skip: out.append(ch)
    return ''.join(out).strip()


OUT.mkdir(parents=True, exist_ok=True)
manifest = []
for fname, title, plant, disease, en in PICKS:
    info = api(dict(action='query', titles=title, prop='imageinfo', iiprop='url|size|mime|sha1|extmetadata',
                    iiextmetadatafilter='LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription'))
    page = next(iter(info['query']['pages'].values()))
    ii = page['imageinfo'][0]; em = ii['extmetadata']
    dest = OUT / fname
    if not dest.exists():
        with urllib.request.urlopen(urllib.request.Request(ii['url'], headers=UA), timeout=120) as r:
            dest.write_bytes(r.read())
    with Image.open(dest) as im:
        im.verify(); fmt = im.format
    with Image.open(dest) as im:
        size = im.size
    assert fmt in {'JPEG', 'PNG'} and dest.stat().st_size <= 10 * 1024 * 1024, fname
    manifest.append(dict(
        file=fname, bytes=dest.stat().st_size, width=size[0], height=size[1],
        sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
        truth=dict(plant=plant, disease=disease, label_en=en),
        expected_answer_vi=f'{plant.capitalize()} · {disease}',
        source=dict(page=ii['descriptionurl'], file_url=ii['url'], author=strip_tags(em.get('Artist', {}).get('value', '')),
                    license=em.get('LicenseShortName', {}).get('value', ''), license_url=em.get('LicenseUrl', {}).get('value', ''),
                    description=strip_tags(em.get('ImageDescription', {}).get('value', ''))[:200],
                    changes='Tải nguyên bản từ Wikimedia Commons, không chỉnh sửa.'),
    ))
    print(f"{fname}: {size[0]}x{size[1]} {dest.stat().st_size // 1024} KB | {manifest[-1]['source']['license']} | {manifest[-1]['source']['author'][:50]}")
(OUT / 'manifest.json').write_text(json.dumps(dict(schema_version=1, purpose='Ảnh để người dùng tự upload khi demo; không nạp vào app.',
                                                   images=manifest), ensure_ascii=False, indent=2) + '\n')
lines = ['# Ảnh để demo chức năng tải ảnh lên', '',
         'Năm ảnh bệnh lá chụp ngoài thực tế, tải từ Wikimedia Commons (giấy phép mở), **không** nạp sẵn vào app:',
         'khi demo, bấm "Tải ảnh của bạn lên" và chọn một ảnh ở đây. Đáp án đúng chỉ gồm loài cây + bệnh (theo nhãn của nguồn).', '',
         '| Ảnh | Đáp án đúng | Nguồn | Tác giả | Giấy phép |', '|---|---|---|---|---|']
for m in manifest:
    s = m['source']
    lines.append(f"| `{m['file']}` | {m['expected_answer_vi']} | [Commons]({s['page']}) | {s['author']} | [{s['license']}]({s['license_url']}) |")
lines += ['', 'Gợi ý câu hỏi (đúng văn phong bộ dữ liệu): "Loại tình trạng bệnh lý nào thể hiện rõ trên lá <cây> này?" hoặc bấm chip "Lá bị bệnh gì?".',
          '', 'Chi tiết (sha256, kích thước, mô tả gốc): `manifest.json`. Tải lại bằng `scripts/fetch_upload_demo.py`.']
(OUT / 'README.md').write_text('\n'.join(lines) + '\n')
print('wrote', OUT / 'manifest.json')
