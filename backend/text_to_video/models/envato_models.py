from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re

class EnvatoMusicTheme(Enum):
    TECHNOLOGY = "technology"
    CORPORATE = "corporate"
    DOCUMENTARY = "documentary"
    ACTION = "action"
    LIFESTYLE = "lifestyle"
    NATURE = "nature"
    DRAMA = "drama"
    SPORTS = "sports"
    FASHION = "fashion"
    TRAVEL = "travel"
    GAMING = "gaming"
    CHILDREN = "children"
    COMEDY = "comedy"
    # Add more as discovered or needed

class EnvatoMusicTempo(Enum):
    VERY_SLOW = "very-slow-(below-60-bpm)"
    SLOW = "slow-(60-90-bpm)"
    MEDIUM = "medium-(90-110-bpm)"
    UPBEAT = "upbeat-(110-140-bpm)"
    FAST = "fast-(140-160-bpm)"
    VERY_FAST = "very-fast-(160-bpm)"
    # Add more as discovered or needed

class EnvatoMusicVocals(Enum):
    NO_VOCALS = "no-vocals"
    INSTRUMENTAL_ONLY = "instrumental-only" # Often same as no-vocals
    BACKGROUND_VOCALS_SAMPLES = "background-vocals-samples"
    LEAD_VOCALS = "lead-vocals"
    # Add more as discovered or needed

class EnvatoMusicGenre(Enum):
    CINEMATIC = "cinematic"
    CORPORATE = "corporate"
    HIP_HOP = "hip-hop"
    ROCK = "rock"
    ELECTRONIC = "electronic"
    AMBIENT = "ambient"
    FUNK = "funk"
    CLASSICAL = "classical"
    POP = "pop"
    JAZZ = "jazz"
    FOLK_ACOUSTIC = "folk-acoustic"
    EXPERIMENTAL = "experimental"
    # Add more as discovered or needed

class EnvatoMusicMood(Enum):
    HAPPY = "happy"
    INSPIRING = "inspiring"
    UPBEAT = "upbeat"
    ANGRY = "angry"
    FUNNY = "funny"
    CHILL = "chill"
    EPIC = "epic"
    DRAMATIC = "dramatic"
    SAD = "sad"
    ROMANTIC = "romantic"
    MYSTERIOUS = "mysterious"
    HOPEFUL = "hopeful"
    # Add more as discovered or needed

class EnvatoMusicSearchParams(BaseModel):
    keyword: str = Field(..., description="The main search keyword(s), e.g., 'uplifting corporate'.")
    themes: Optional[List[EnvatoMusicTheme]] = None
    tempos: Optional[List[EnvatoMusicTempo]] = None
    vocals: Optional[List[EnvatoMusicVocals]] = None # Envato seems to treat vocals as multi-select, though often one is chosen.
    genres: Optional[List[EnvatoMusicGenre]] = None
    moods: Optional[List[EnvatoMusicMood]] = None
    max_length: Optional[str] = Field(None, description="Maximum length in MM:SS format, e.g., '01:30' for 1 min 30 secs. 'any' for no limit.")
    min_length: Optional[str] = Field(None, description="Minimum length in MM:SS format, e.g., '00:30' for 30 secs.")

    @field_validator('max_length', 'min_length')
    @classmethod
    def validate_length_format(cls, v):
        if v is None or v.lower() == 'any':
            return v
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Length must be in MM:SS format or 'any'")
        # Further validation could check if MM is 00-99 and SS is 00-59
        minutes, seconds = map(int, v.split(':'))
        if not (0 <= minutes <= 99 and 0 <= seconds <= 59):
            raise ValueError("Invalid MM:SS time format.")
        return v

    def build_url_path(self) -> str:
        base_path = "/audio/"

        keyword_path = self.keyword.replace(" ", "+")
        path_segments = [keyword_path]

        filter_map = {
            "theme": self.themes,
            "tempo": self.tempos,
            "vocals": self.vocals,
            "genre": self.genres,
            "mood": self.moods,
        }

        for filter_name, filter_values in filter_map.items():
            if filter_values:
                value_str = "+".join([val.value for val in filter_values])
                path_segments.append(f"{filter_name}-{value_str}")

        # Length parameters are different
        # Example: /length-00:30-01:30 (min-max)
        # Or: /max-length-01:30
        # Or: /min-length-00:30
        if self.min_length and self.min_length.lower() != 'any' and self.max_length and self.max_length.lower() != 'any':
            path_segments.append(f"length-{self.min_length}-{self.max_length}")
        elif self.min_length and self.min_length.lower() != 'any':
            path_segments.append(f"min-length-{self.min_length}")
        elif self.max_length and self.max_length.lower() != 'any':
            path_segments.append(f"max-length-{self.max_length}")

        return base_path + "/".join(path_segments)

# Example Usage (for testing the model itself):
if __name__ == "__main__":
    params1 = EnvatoMusicSearchParams(keyword="epic action trailer")
    print(f"Params 1 URL path: {params1.build_url_path()}")
    # Expected: /audio/epic+action+trailer

    params2 = EnvatoMusicSearchParams(
        keyword="inspiring background corporate",
        themes=[EnvatoMusicTheme.CORPORATE, EnvatoMusicTheme.LIFESTYLE],
        tempos=[EnvatoMusicTempo.UPBEAT],
        genres=[EnvatoMusicGenre.CORPORATE, EnvatoMusicGenre.ELECTRONIC],
        moods=[EnvatoMusicMood.INSPIRING, EnvatoMusicMood.HOPEFUL],
        max_length="02:00",
        min_length="00:45"
    )
    print(f"Params 2 URL path: {params2.build_url_path()}")
    # Expected: /audio/inspiring+background+corporate/theme-corporate+lifestyle/tempo-upbeat-(110-140-bpm)/genre-corporate+electronic/mood-inspiring+hopeful/length-00:45-02:00

    params3 = EnvatoMusicSearchParams(
        keyword="chill study beats",
        genres=[EnvatoMusicGenre.HIP_HOP, EnvatoMusicGenre.AMBIENT],
        moods=[EnvatoMusicMood.CHILL],
        vocals=[EnvatoMusicVocals.NO_VOCALS]
    )
    print(f"Params 3 URL path: {params3.build_url_path()}")
    # Expected: /audio/chill+study+beats/vocals-no-vocals/genre-hip-hop+ambient/mood-chill

    try:
        params_invalid_length = EnvatoMusicSearchParams(keyword="test", max_length="1:30") # Invalid format
    except ValueError as e:
        print(f"Caught expected validation error for length: {e}")

    try:
        params_invalid_time = EnvatoMusicSearchParams(keyword="test", min_length="00:60") # Invalid time
    except ValueError as e:
        print(f"Caught expected validation error for time: {e}")

# --- Video Models ---
class EnvatoVideoCategory(Enum):
    STOCK_FOOTAGE = "stock-footage"
    MOTION_GRAPHICS = "motion-graphics"
    # Add more if discovered, e.g., video-templates, apple-motion etc.

class EnvatoVideoOrientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    SQUARE = "square"

class EnvatoVideoResolution(Enum):
    # Values based on typical URL slugs observed
    HD_720P = "720p-(hd)" # Guessing, confirm if needed
    HD_1080P = "1080p-(full-hd)"
    UHD_4K = "4k-(uhd)"
    UHD_8K = "8k-(uhd)" # Guessing, confirm if needed

class EnvatoStockVideoSearchParams(BaseModel):
    keyword: str = Field(..., description="The main search keyword(s).")
    category: EnvatoVideoCategory = Field(..., description="The category of video to search for.")
    orientation: Optional[EnvatoVideoOrientation] = None
    resolutions: Optional[List[EnvatoVideoResolution]] = None
    min_length: Optional[str] = Field(None, description="Minimum length in MM:SS format, e.g., '00:15'.")
    max_length: Optional[str] = Field(None, description="Maximum length in MM:SS format, e.g., '01:00'.")

    @field_validator('min_length', 'max_length')
    @classmethod
    def validate_video_length_format(cls, v):
        if v is None or v.lower() == 'any': # Allow 'any' or None
            return v
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Length must be in MM:SS format or 'any'.")
        minutes, seconds = map(int, v.split(':'))
        if not (0 <= minutes <= 99 and 0 <= seconds <= 59):
            raise ValueError("Invalid MM:SS time format for video length.")
        return v

    def build_url_path(self) -> str:
        # Base path: elements.envato.com/stock-video/{category}/{keyword}/...
        base_path = f"/stock-video/{self.category.value}/"
        keyword_path = self.keyword.replace(" ", "+")
        path_segments = [keyword_path]

        if self.orientation:
            path_segments.append(f"orientation-{self.orientation.value}")

        if self.resolutions:
            # Resolutions are joined by '+' for OR logic, e.g., resolution-4k-(uhd)+1080p-(full-hd)
            value_str = "+".join([res.value for res in self.resolutions])
            path_segments.append(f"resolution-{value_str}")

        # Length parameters
        if self.min_length and self.min_length.lower() != 'any' and self.max_length and self.max_length.lower() != 'any':
            path_segments.append(f"min-length-{self.min_length}/max-length-{self.max_length}") # Note: Envato seems to use separate path segments for these
        elif self.min_length and self.min_length.lower() != 'any':
            path_segments.append(f"min-length-{self.min_length}")
        elif self.max_length and self.max_length.lower() != 'any':
            path_segments.append(f"max-length-{self.max_length}")

        return base_path + "/".join(path_segments)

# Example Usage for Video Models:
if __name__ == "__main__":
    # ... (existing music examples) ...
    print("\n--- Video Examples ---")
    vid_params1 = EnvatoStockVideoSearchParams(keyword="city timelapse", category=EnvatoVideoCategory.STOCK_FOOTAGE)
    print(f"Video Params 1 URL: {vid_params1.build_url_path()}")
    # Expected: /stock-video/stock-footage/city+timelapse

    vid_params2 = EnvatoStockVideoSearchParams(
        keyword="abstract background loop",
        category=EnvatoVideoCategory.MOTION_GRAPHICS,
        orientation=EnvatoVideoOrientation.HORIZONTAL,
        resolutions=[EnvatoVideoResolution.HD_1080P, EnvatoVideoResolution.UHD_4K],
        min_length="00:10",
        max_length="00:30"
    )
    print(f"Video Params 2 URL: {vid_params2.build_url_path()}")
    # Expected: /stock-video/motion-graphics/abstract+background+loop/orientation-horizontal/resolution-1080p-(full-hd)+4k-(uhd)/min-length-00:10/max-length-00:30

    vid_params3 = EnvatoStockVideoSearchParams(
        keyword="nature drone shot",
        category=EnvatoVideoCategory.STOCK_FOOTAGE,
        resolutions=[EnvatoVideoResolution.UHD_4K]
    )
    print(f"Video Params 3 URL: {vid_params3.build_url_path()}")
    # Expected: /stock-video/stock-footage/nature+drone+shot/resolution-4k-(uhd)
