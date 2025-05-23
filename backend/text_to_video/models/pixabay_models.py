from typing import List, Optional, Dict
from pydantic import BaseModel, HttpUrl, field_validator

# Common Search Parameters
class PixabayBaseSearchParams(BaseModel):
    key: str
    q: Optional[str] = None
    lang: Optional[str] = None # cs, da, de, en, es, fr, id, it, hu, nl, no, pl, pt, ro, sk, fi, sv, tr, vi, th, bg, ru, el, ja, ko, zh. Default: en
    id: Optional[str] = None
    category: Optional[str] = None # backgrounds, fashion, nature, science, education, feelings, health, people, religion, places, animals, industry, computer, food, sports, transportation, travel, buildings, business, music
    min_width: Optional[int] = None
    min_height: Optional[int] = None
    editors_choice: Optional[bool] = None
    safesearch: Optional[bool] = None
    order: Optional[str] = None # popular, latest. Default: popular
    page: Optional[int] = None
    per_page: Optional[int] = None # 3-200. Default: 20
    pretty: Optional[bool] = None # For debugging

class PixabayImageSearchParams(PixabayBaseSearchParams):
    image_type: Optional[str] = None # all, photo, illustration, vector. Default: all
    orientation: Optional[str] = None # all, horizontal, vertical. Default: all
    colors: Optional[str] = None # comma-separated: "grayscale", "transparent", "red", ..., "black", "brown"

class PixabayVideoSearchParams(PixabayBaseSearchParams):
    video_type: Optional[str] = None # all, film, animation. Default: all


# Response Models for Images
class PixabayImageHit(BaseModel):
    id: int
    pageURL: HttpUrl
    type: str
    tags: str
    previewURL: HttpUrl
    previewWidth: int
    previewHeight: int
    webformatURL: HttpUrl
    webformatWidth: int
    webformatHeight: int
    largeImageURL: HttpUrl
    imageWidth: int
    imageHeight: int
    imageSize: int
    views: int
    downloads: int
    likes: int
    comments: int
    user_id: int
    user: str
    userImageURL: Optional[HttpUrl] = None
    # These might not always be present if full API access is not granted for the key
    fullHDURL: Optional[HttpUrl] = None
    imageURL: Optional[HttpUrl] = None
    vectorURL: Optional[HttpUrl] = None

    @field_validator("userImageURL", mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v


class PixabayImageSearchResponse(BaseModel):
    total: int
    totalHits: int
    hits: List[PixabayImageHit]


# Response Models for Videos
class PixabayVideoFileDetail(BaseModel):
    url: HttpUrl
    width: int
    height: int
    size: int
    thumbnail: Optional[HttpUrl] = None # Thumbnail seems to be part of specific video size in example, added here for completeness if structure varies.

class PixabayVideoVersions(BaseModel):
    large: Optional[PixabayVideoFileDetail] = None
    medium: PixabayVideoFileDetail
    small: PixabayVideoFileDetail
    tiny: PixabayVideoFileDetail

class PixabayVideoHit(BaseModel):
    id: int
    pageURL: HttpUrl
    type: str # film, animation
    tags: str
    duration: int # in seconds
    videos: PixabayVideoVersions
    views: int
    downloads: int
    likes: int
    comments: int
    user_id: int
    user: str
    userImageURL: Optional[HttpUrl] = None

    @field_validator("userImageURL", mode='before')
    @classmethod
    def empty_str_to_none_video(cls, v):
        if v == "":
            return None
        return v

class PixabayVideoSearchResponse(BaseModel):
    total: int
    totalHits: int
    hits: List[PixabayVideoHit]
