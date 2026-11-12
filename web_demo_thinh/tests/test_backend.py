"""Test backend "Hỏi Lá" ở chế độ không model (PVVQA_DEMO_NO_GPU=1) và module upload."""
import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['PVVQA_DEMO_NO_GPU'] = '1'

from hoila.uploads import UploadStore  # noqa: E402


def png_bytes(size=(64, 48), fmt='PNG'):
    buf = io.BytesIO()
    Image.new('RGB', size, (20, 120, 40)).save(buf, fmt)
    return buf.getvalue()


def test_upload_store_accepts_png_and_resizes():
    store = UploadStore(max_bytes=1024 * 1024, max_side=32)
    try:
        info = store.add(png_bytes((300, 100)))
        assert info['image_id'].startswith('upload_')
        assert max(info['width'], info['height']) == 32
        path = store.path(info['image_id'])
        assert path and path.is_file()
        store.remove(info['image_id'])
        assert store.path(info['image_id']) is None
        assert not path.exists()
    finally:
        store.close()


def test_upload_store_rejects_non_image_and_oversize():
    store = UploadStore(max_bytes=10, max_side=32)
    try:
        with pytest.raises(ValueError):
            store.add(b'not an image at all')
        with pytest.raises(ValueError):
            store.add(png_bytes())  # > 10 byte
    finally:
        store.close()


def test_upload_store_rejects_gif():
    store = UploadStore()
    try:
        with pytest.raises(ValueError):
            store.add(png_bytes(fmt='GIF'))
    finally:
        store.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from hoila.app import create_app
    with TestClient(create_app()) as c:
        yield c


def test_content_and_samples(client):
    runtime = client.get('/api/runtime').json()
    assert runtime['inference_ready'] is False and runtime['state'] == 'unavailable'
    assert runtime['uploads_enabled'] is False
    samples = client.get('/api/samples').json()
    assert len(samples) >= 9
    assert all('reference' not in q for s in samples for q in s['questions'])
    first = samples[0]
    assert client.get(first['asset_url']).status_code == 200
    assert client.get('/api/assets/../configs/web_demo.yaml').status_code in {404, 422}
    content = client.get('/api/content').json()
    assert content['language'] == 'vi'


def test_inference_rejected_without_model(client):
    r = client.post('/api/inferences', json=dict(image_id='image_046993.JPG', question_id='row_017244',
                                                 model_ids=['nora']))
    assert r.status_code == 503
    assert r.json()['error']['code'] == 'MODEL_NOT_READY'
    r = client.post('/api/inferences', json=dict(image_id='khong-co', question=None, question_id=None,
                                                 model_ids=['nora']))
    assert r.status_code == 422


def test_upload_disabled_in_content_only_mode(client):
    r = client.post('/api/uploads', files={'file': ('leaf.png', png_bytes(), 'image/png')})
    assert r.status_code == 503
    assert r.json()['error']['code'] == 'UPLOADS_DISABLED'


def test_pages_and_404(client):
    assert client.get('/khong-ton-tai').status_code == 404
    r = client.get('/hoi-dap')
    assert r.status_code in {200, 503}  # 503 nếu frontend chưa build
