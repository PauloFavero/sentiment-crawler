from typing import Dict, List, Any, TypedDict, Optional

class Comment(TypedDict):
    body: str
    id: str
    
class Post(TypedDict):
    id: str
    title: Optional[str]
    text: Optional[str]
    selftext: Optional[str]
    comments: List[Comment]
    source: str
    sentiment_score: Optional[float]
    analysis: Optional[Any] 