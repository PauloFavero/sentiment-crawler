from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Author(BaseModel):
    """Common author model for both platforms"""
    id: str
    name: Optional[str] = Field(default="[deleted]")
    platform_specific_data: Optional[dict] = None

class Reply(BaseModel):
    """Model for replies/comments to main content"""
    id: str
    content: str
    author: Author
    score: int = 0
    created_at: float
    platform: str = Field(..., description="Platform identifier (reddit/twitter)")
    platform_specific_data: Optional[dict] = None

class Content(BaseModel):
    """Main content model that works for both tweets and reddit posts"""
    id: str
    title: Optional[str] = None  # For Reddit posts
    text: str  # Main content (tweet text or Reddit selftext)
    author: Author
    created_at: float
    score: int = 0
    url: Optional[str] = None
    platform: str = Field(..., description="Platform identifier (reddit/twitter)")
    engagement_metrics: dict = Field(default_factory=dict)  # For likes, retweets, etc.
    replies: List[Reply] = Field(default_factory=list)
    platform_specific_data: Optional[dict] = None

class ScrapedData(BaseModel):
    """Container for scraped content from any platform"""
    platform: str = Field(..., description="Platform identifier (reddit/twitter)")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    items: List[Content]
    metadata: Optional[dict] = None 