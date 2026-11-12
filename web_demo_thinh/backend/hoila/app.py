"""FastAPI cho demo "Hỏi Lá". Dựa trên pvvqa/web/app.py của Khoa.

Thêm: POST /api/uploads (ảnh người dùng), thông điệp tiếng Việt, route trang tiếng Việt.
Client vẫn không được chọn đường dẫn file trên máy hay đổi tham số sinh.
"""
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .data import ROOT, DemoData, settings
from .jobs import JobManager
from .uploads import UploadStore

PAGES = {'', 'hoi-dap', 'bo-du-lieu', 'phuong-phap', 'ket-qua'}


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_id: Annotated[str, Field(min_length=1, max_length=100)]
    question_id: str | None = None
    question: Annotated[str | None, Field(max_length=500)] = None
    model_ids: Annotated[list[str], Field(min_length=1, max_length=4)]


def create_app(manager=None):
    cfg = settings()
    disabled = os.environ.get('PVVQA_DEMO_NO_GPU') == '1'
    uploads = UploadStore(max_bytes=cfg.get('upload_max_bytes', 10 * 1024 * 1024),
                          max_side=cfg.get('upload_max_side', 1024))
    data = DemoData(uploads=uploads)
    jobs = manager or JobManager(cfg, data, disabled=disabled)

    @asynccontextmanager
    async def lifespan(app):
        jobs.start()
        yield
        jobs.close()
        uploads.close()

    app = FastAPI(title='Hỏi Lá — Hỏi đáp bệnh lá cây bằng tiếng Việt', lifespan=lifespan)
    app.state.jobs = jobs
    app.state.uploads = uploads

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc):
        return JSONResponse(status_code=422, content=dict(error=dict(
            code='INVALID_INPUT', message='Kiểm tra lại các trường gửi lên; câu hỏi tối đa 500 ký tự.')))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        return JSONResponse(status_code=exc.status_code, content=dict(error=exc.detail))

    def error(status, code, message):
        raise HTTPException(status, detail=dict(code=code, message=message))

    @app.get('/health')
    def health():
        return dict(status='ok')

    @app.get('/api/runtime')
    def runtime():
        return jobs.runtime()

    @app.get('/api/models')
    def models():
        state = jobs.runtime()
        return [dict(id=key, label=val['label'], available=state['inference_ready'], use_nora=val['use_nora'])
                for key, val in cfg['models'].items()]

    @app.get('/api/content')
    def content():
        return dict(title='Hỏi Lá', language='vi', report_version=data.results['version'],
                    assets={key: f'/api/assets/{key}' for key in data.assets})

    @app.get('/api/results')
    def results():
        return data.results

    @app.get('/api/samples')
    def samples():
        return data.public_samples()

    @app.get('/api/assets/{asset_id}')
    def asset(asset_id: str):
        path = data.assets.get(asset_id)
        if not path or not path.is_file():
            error(404, 'ASSET_NOT_FOUND', 'Không có hình này.')
        return FileResponse(path, headers={'Cache-Control': 'public, max-age=3600'})

    @app.post('/api/uploads', status_code=201)
    async def upload(file: UploadFile = File(...)):
        if disabled:
            error(503, 'UPLOADS_DISABLED', 'Tải ảnh lên chỉ dùng được khi demo chạy model trên máy.')
        limit = uploads.max_bytes
        chunks, total = [], 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                error(413, 'UPLOAD_TOO_LARGE', f'Ảnh vượt quá {limit // (1024 * 1024)} MB.')
            chunks.append(chunk)
        try:
            result = uploads.add(b''.join(chunks))
        except ValueError as exc:
            error(422, 'INVALID_IMAGE', str(exc))
        return result

    @app.post('/api/inferences', status_code=202)
    def infer(body: InferenceRequest):
        try:
            result = jobs.submit(**body.model_dump())
        except ValueError as exc:
            error(422, 'INVALID_INPUT', str(exc))
        except OverflowError as exc:
            error(429, 'QUEUE_FULL', str(exc))
        except RuntimeError as exc:
            error(503, 'MODEL_NOT_READY', str(exc))
        return dict(job_id=result['job_id'], status_url=f"/api/inferences/{result['job_id']}", status=result['status'])

    @app.get('/api/inferences/{job_id}')
    def job(job_id: str):
        try:
            return jobs.get(job_id)
        except KeyError:
            error(404, 'JOB_NOT_FOUND', 'Lượt hỏi này đã hết hạn hoặc server vừa khởi động lại. Hãy hỏi lại.')

    @app.delete('/api/inferences/{job_id}')
    def cancel(job_id: str):
        try:
            return jobs.cancel(job_id)
        except KeyError:
            error(404, 'JOB_NOT_FOUND', 'Lượt hỏi này không còn nữa.')

    dist = ROOT / 'frontend/dist'
    if (dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='frontend-assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path not in PAGES:
            error(404, 'NOT_FOUND', 'Trang này không tồn tại.')
        if not (dist / 'index.html').is_file():
            error(503, 'FRONTEND_NOT_BUILT', 'Hãy build frontend trước khi mở demo.')
        return FileResponse(dist / 'index.html', headers={'Cache-Control': 'no-cache'})

    return app


app = create_app()
