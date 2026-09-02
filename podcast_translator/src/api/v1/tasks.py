import asyncio
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect

from src.core.database import AsyncSessionLocal
from src.core.exceptions import (
    FeatureDisabledError,
    QuotaExceededError,
    ResourceNotFoundError,
    TaskDispatchError,
    TooManyActiveTasksError,
    ValidationError,
)
from src.core.redis import get_redis_async, get_task_progress_channel
from src.core.security import decode_token
from src.dependencies import get_current_user, get_task_service
from src.models.user import User
from src.schemas.task import TaskResponse, TaskResumeRequest, TaskSegmentResponse
from src.services.task_runtime_service import TaskRuntimeService
from src.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(
    file: UploadFile = File(...),
    config: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        try:
            config_dict = json.loads(config) if config else {}
        except json.JSONDecodeError as exc:
            raise ValidationError("Invalid upload config payload") from exc
        return await task_service.create_task(current_user.id, file, config_dict)
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except QuotaExceededError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except TooManyActiveTasksError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to create task")
        raise HTTPException(status_code=500, detail="Failed to create task. Please try again later.")


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    limit = max(1, min(limit, 100))
    skip = max(0, skip)
    return await task_service.list_tasks(current_user.id, skip, limit)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        return await task_service.get_task(task_id, current_user.id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/{task_id}/segments", response_model=List[TaskSegmentResponse])
async def get_task_segments(
    task_id: uuid.UUID,
    skip: int = 0,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    limit = max(1, min(limit, 500))
    skip = max(0, skip)
    try:
        return await task_service.get_task_segments(task_id, current_user.id, skip, limit)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(
    task_id: uuid.UUID,
    request: TaskResumeRequest | None = Body(None),
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        return await task_service.resume_task(
            task_id,
            current_user.id,
            config_updates=request.config if request else None,
        )
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TaskDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        return await task_service.request_pause(task_id, current_user.id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    try:
        await task_service.delete_task(task_id, current_user.id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.websocket("/{task_id}/ws")
async def websocket_endpoint(websocket: WebSocket, task_id: str, token: Optional[str] = Query(None)):
    await websocket.accept()

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        payload = decode_token(token)
        if payload.get("token_type") != "access":
            raise ValueError("Invalid token type")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("Missing subject")
        user_id = uuid.UUID(user_id_str)
        task_uuid = uuid.UUID(task_id)
    except Exception:
        await websocket.close(code=4003, reason="Invalid or expired token")
        return

    redis_client = get_redis_async()
    if redis_client is None:
        await websocket.close(code=1011, reason="Redis is unavailable")
        return

    async with AsyncSessionLocal() as session:
        runtime_service = TaskRuntimeService(session)
        try:
            snapshot = await runtime_service.get_task_progress_payload_for_user(task_uuid, user_id)
        except ResourceNotFoundError:
            await websocket.close(code=4004, reason="Task not found")
            return

    await websocket.send_json(snapshot)

    channel = get_task_progress_channel(task_id)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.25)
            except asyncio.TimeoutError:
                pass

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        return
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
