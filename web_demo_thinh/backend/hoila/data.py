"""Dữ liệu mẫu, tài nguyên ảnh và cấu hình. Dựa trên pvvqa/web/data.py của Khoa.

Khác biệt: gốc repo là web_demo_thinh/, không có translations.json, có thêm ảnh người dùng tải lên.
"""
import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / 'generated'


def settings():
    cfg = yaml.safe_load(Path(os.environ.get('PVVQA_WEB_CONFIG', ROOT / 'configs/web_demo.yaml')).read_text())
    if os.environ.get('PVVQA_DEMO_BASE'):
        cfg['base_model'] = os.environ['PVVQA_DEMO_BASE']
    return cfg


def read_json(name):
    return json.loads((GENERATED / name).read_text())


class DemoData:
    def __init__(self, uploads=None):
        self.uploads = uploads
        self.samples = {row['row_id']: row for row in read_json('samples.json')}
        self.assets = {key: (ROOT / value).resolve() for key, value in read_json('assets.json').items()}
        self.real_world = {}
        sample_dir = ROOT / 'samples/real-world'
        manifest = json.loads((sample_dir / 'manifest.json').read_text())
        for image in manifest['images']:
            image_id = image['image_id']
            path = (sample_dir / image_id).resolve()
            if not path.is_relative_to(sample_dir.resolve()) or image_id in self.assets:
                raise ValueError('Invalid real-world image asset')
            if hashlib.sha256(path.read_bytes()).hexdigest() != image['image_sha256']:
                raise ValueError(f'Real-world image checksum mismatch: {image_id}')
            self.assets[image_id] = path
            self.real_world[image_id] = image
            for question in image['questions']:
                if question['row_id'] in self.samples:
                    raise ValueError('Duplicate sample question ID')
                self.samples[question['row_id']] = dict(
                    **question, image_id=image_id, asset_id=image_id, reference=None)
        if any(not path.is_relative_to(ROOT) for path in self.assets.values()):
            raise ValueError('Assets must remain within the repository')
        self.results = read_json('results.json')
        self.sample_image_ids = {row['image_id'] for row in self.samples.values()}

    def public_samples(self):
        images = {}
        for sample in self.samples.values():
            image = images.setdefault(sample['image_id'], dict(image_id=sample['image_id'],
                                      asset_url=f"/api/assets/{sample['asset_id']}", questions=[]))
            extra = self.real_world.get(sample['image_id'])
            image['group'] = 'real-world' if extra else 'plantvillage'
            if extra:
                image.update(label=extra.get('label_vi', extra['label']), source=extra['source'],
                             truth=extra.get('truth'))
            image['questions'].append({key: sample[key] for key in ['row_id', 'question', 'question_type']})
            if 'question_style' in sample:
                image['questions'][-1]['question_style'] = sample['question_style']
        return list(images.values())

    def is_upload(self, image_id):
        return isinstance(image_id, str) and image_id.startswith('upload_')

    def image_path(self, image_id):
        """Đường dẫn file ảnh cho ảnh mẫu hoặc ảnh tải lên; None nếu không có."""
        if self.is_upload(image_id):
            return self.uploads.path(image_id) if self.uploads else None
        return self.assets.get(image_id) if image_id in self.sample_image_ids else None

    def resolve_input(self, image_id, question_id, question):
        if self.image_path(image_id) is None:
            if self.is_upload(image_id):
                raise ValueError('Ảnh tải lên đã hết hạn. Hãy tải lại ảnh rồi hỏi lần nữa.')
            raise ValueError('Hãy chọn một ảnh trong bộ ảnh mẫu hoặc tải ảnh lên.')
        if question_id:
            sample = self.samples.get(question_id)
            if not sample or sample['image_id'] != image_id or question is not None:
                raise ValueError('Câu hỏi gợi ý phải thuộc về ảnh đang chọn.')
            return sample['question'], sample['reference']
        if not question or not 1 <= len(question.strip()) <= 500:
            raise ValueError('Hãy nhập câu hỏi từ 1 đến 500 ký tự.')
        return question.strip(), None
