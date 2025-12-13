from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class TopicCreate(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class TopicOut(BaseModel):
    id: str
    name: str
    keywords: list[str]
    exclude_keywords: list[str]
    created_at: str
    updated_at: str


class JobCreate(BaseModel):
    topic_id: str
    schedule: str
    enabled: bool = True
    actions: dict = Field(default_factory=dict)


class JobOut(BaseModel):
    id: str
    topic_id: str
    schedule: str
    enabled: bool
    like_enabled: bool
    comment_enabled: bool
    created_at: str
    updated_at: str


class RunCreate(BaseModel):
    job_id: str


class RunOut(BaseModel):
    id: str
    job_id: str
    status: str
    started_at: str
    ended_at: str | None


class CandidateIn(BaseModel):
    source: Literal["search", "feed"]
    url: str
    video_id: str | None = None
    author_name: str | None = None
    title: str | None = None
    raw_text: str | None = None
    evidence: dict | None = None


class CandidateBatchUpsert(BaseModel):
    run_id: str
    items: list[CandidateIn]


class CandidateBatchUpsertResp(BaseModel):
    candidate_ids: list[str]


ActionType = Literal["like", "comment_submit"]
ActionTaskStatus = Literal["queued", "running", "succeeded", "failed", "review_required", "cancelled"]


class ActionTaskNextReq(BaseModel):
    account_id: str = "default"


class ActionTaskOut(BaseModel):
    id: str
    candidate_id: str
    candidate_url: str | None = None
    candidate_title: str | None = None
    action_type: ActionType
    payload: dict


class ActionTaskNextResp(BaseModel):
    task: ActionTaskOut | None


class ActionTaskReportReq(BaseModel):
    status: Literal["succeeded", "failed", "review_required"]
    error_message: str | None = None
    evidence: dict | None = None


class CommentTemplateCreate(BaseModel):
    name: str
    body: str
    enabled: bool = True


class CommentTemplateOut(BaseModel):
    id: str
    name: str
    body: str
    enabled: bool
    created_at: str
    updated_at: str


