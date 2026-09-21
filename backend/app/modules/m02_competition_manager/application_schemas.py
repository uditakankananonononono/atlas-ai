"""HTTP boundary models for the opportunity application browser workflow.

Every model is strict and every payload passes the credential gate: Atlas
never accepts passwords, MFA codes, cookies, or tokens in API payloads - the
owner types those only into their own paired browser session.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.m13_browser_agent.application_flow import assert_no_credentials


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationSessionCreateIn(StrictModel):
    competition_id: str | None = Field(default=None, min_length=1, max_length=120)
    opportunity_id: str | None = Field(default=None, min_length=1, max_length=120)
    application_url: str | None = Field(default=None, min_length=1, max_length=4096)
    label: str = Field(default="", max_length=300)


class ApplicationResumeIn(StrictModel):
    login_confirmed: bool

    @field_validator("login_confirmed")
    @classmethod
    def must_be_explicit(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("login must be explicitly confirmed to resume")
        return value


class ApplicationStageIn(StrictModel):
    fields: dict[str, str] = Field(min_length=1, max_length=200)
    submit_selector: str = Field(min_length=1, max_length=500)

    @field_validator("fields")
    @classmethod
    def no_credentials_and_bounded(cls, fields: dict[str, str]) -> dict[str, str]:
        assert_no_credentials(fields)
        if any(len(key) > 300 or len(value) > 10000 for key, value in fields.items()):
            raise ValueError("form data is too large")
        return fields


class ApplicationSubmitIn(StrictModel):
    approval_id: str = Field(min_length=1, max_length=200)

    @field_validator("approval_id")
    @classmethod
    def no_credentials(cls, value: str) -> str:
        assert_no_credentials({"approval_id": value})
        return value
