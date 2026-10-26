from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


RepositoryProvider = Literal[
    "GitHub",
    "GitLab",
    "Bitbucket",
    "Azure DevOps",
]


class RepositoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=10, max_length=500)
    provider: RepositoryProvider
    branch: str = Field(default="main", min_length=1, max_length=200)
    access_token: str | None = Field(default=None, exclude=True)

    @field_validator("name", "branch")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        if any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not allowed.")

        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)

        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("A valid HTTPS repository URL is required.")

        if parsed.username or parsed.password:
            raise ValueError("Do not include credentials in the URL.")

        if parsed.query or parsed.fragment:
            raise ValueError("Query strings and fragments are not allowed.")

        return value.rstrip("/")


class RepositoryRegistrationResponse(BaseModel):
    id: str
    name: str
    url: str
    provider: RepositoryProvider
    branch: str
    status: Literal["Registered", "Cloning", "Analyzing", "Analysis Complete", "Failed"]
    created_at: datetime
