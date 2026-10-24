"""Load and validate the portfolio content from content.yaml."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONTENT_PATH = BASE_DIR / "content.yaml"


class Site(BaseModel):
    title: str
    description: str
    source_url: Optional[str] = None
    # Public address of the live site, used for the canonical link and
    # absolute link-preview URLs.
    url: Optional[str] = None
    # Link-preview image: a full URL, or a path relative to app/static/.
    image: Optional[str] = None

    @property
    def page_url(self) -> Optional[str]:
        """The live site's address, always with exactly one trailing slash."""
        return self.url.rstrip("/") + "/" if self.url else None

    @property
    def image_url(self) -> Optional[str]:
        """Absolute URL of the link-preview image, or None."""
        if not self.image:
            return None
        if self.image.startswith(("http://", "https://")):
            return self.image
        if not self.url:
            return None
        return f"{self.page_url}static/{self.image.lstrip('/')}"


class Profile(BaseModel):
    name: str
    initials: str
    headline: str
    location: str
    availability: str
    intro: str


class CV(BaseModel):
    file: str
    download_name: str


class SkillGroup(BaseModel):
    group: str
    items: list[str]


class Project(BaseModel):
    slug: str
    title: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    repo_url: Optional[str] = None
    period: Optional[str] = None
    status: Literal["public", "private"] = "public"
    note: Optional[str] = None


class Job(BaseModel):
    role: str
    company: str
    period: str
    points: list[str] = Field(default_factory=list)


class Photo(BaseModel):
    jpg: str
    webp: Optional[str] = None
    alt: str
    width: int
    height: int


class Education(BaseModel):
    degree: str
    school: str
    period: str
    details: Optional[str] = None
    photo: Optional[Photo] = None


class Language(BaseModel):
    name: str
    level: str


class Contact(BaseModel):
    email: str
    linkedin: str
    github: str


class Content(BaseModel):
    site: Site
    profile: Profile
    cv: CV
    about: list[str]
    skills: list[SkillGroup]
    projects: list[Project]
    experience: list[Job]
    education: list[Education]
    languages: list[Language]
    contact: Contact


def content_path() -> Path:
    """The content file in use: $CONTENT_PATH if set, else content.yaml in the project root."""
    return Path(os.environ.get("CONTENT_PATH", DEFAULT_CONTENT_PATH))


@lru_cache(maxsize=1)
def load_content() -> Content:
    with content_path().open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return Content.model_validate(data)
