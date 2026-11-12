"""Ảnh người dùng tải lên (chỉ bản chạy trên máy).

Quy tắc (docs/WEB_DEMO_HANDOFF.md mục 5): kiểm tra nội dung JPEG/PNG, giới hạn dung lượng, thu nhỏ trước
khi đưa vào processor; không lưu lâu dài, không ghi log nội dung ảnh. File nằm trong thư mục tạm, bị xoá
ngay khi lượt hỏi dùng nó kết thúc, khi hết hạn, hoặc khi tắt server.
"""
import shutil
import tempfile
import threading
import time
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {'JPEG', 'PNG'}


class UploadStore:
    def __init__(self, max_bytes=10 * 1024 * 1024, max_side=1024, ttl=600, limit=16):
        self.max_bytes, self.max_side, self.ttl, self.limit = max_bytes, max_side, ttl, limit
        self.dir = Path(tempfile.mkdtemp(prefix='hoila-uploads-'))
        self.items = {}
        self.lock = threading.Lock()

    def add(self, data):
        if len(data) > self.max_bytes:
            raise ValueError(f'Ảnh vượt quá {self.max_bytes // (1024 * 1024)} MB. Hãy chọn ảnh nhỏ hơn.')
        try:
            with Image.open(BytesIO(data)) as probe:
                probe.verify()
                fmt = probe.format
            with Image.open(BytesIO(data)) as image:
                if fmt not in ALLOWED_FORMATS:
                    raise ValueError('Chỉ nhận ảnh JPG hoặc PNG.')
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((self.max_side, self.max_side))
                width, height = image.size
                upload_id = f'upload_{uuid.uuid4().hex}'
                path = self.dir / f'{upload_id}.jpg'
                image.save(path, 'JPEG', quality=92)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValueError('Tệp không phải ảnh JPG/PNG hợp lệ.')
        with self.lock:
            self._prune_locked()
            self.items[upload_id] = dict(path=path, created_at=time.monotonic())
        return dict(image_id=upload_id, width=width, height=height)

    def path(self, upload_id):
        with self.lock:
            self._prune_locked()
            item = self.items.get(upload_id)
            return item['path'] if item else None

    def remove(self, upload_id):
        with self.lock:
            item = self.items.pop(upload_id, None)
        if item:
            item['path'].unlink(missing_ok=True)

    def _prune_locked(self):
        now = time.monotonic()
        expired = [key for key, item in self.items.items() if now - item['created_at'] > self.ttl]
        oldest = sorted(self.items, key=lambda key: self.items[key]['created_at'])
        for key in expired + oldest[:max(0, len(self.items) - self.limit + 1)]:
            item = self.items.pop(key, None)
            if item:
                item['path'].unlink(missing_ok=True)

    def close(self):
        with self.lock:
            self.items.clear()
        shutil.rmtree(self.dir, ignore_errors=True)
