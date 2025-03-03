from datetime import datetime
from temporalio import activity
import asyncpraw
import os

@activity.defn
async def say_hello(name: str) -> str:
    return f"Hello {name} at {datetime.now()}"

@activity.defn
async def scrape_reddit() -> list:
    # Initialize Reddit client with asyncpraw
    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="my_reddit_scraper/1.0"
    )
    
    # Get top posts from a subreddit (example with 'programming')
    subreddit = await reddit.subreddit("programming")
    posts = []
    
    # Use async iteration for hot posts
    async for post in subreddit.hot(limit=10):  # Get top 10 hot posts
        posts.append({
            "title": post.title,
            "score": post.score,
            "url": post.url,
            "created_utc": post.created_utc
        })
    
    # Close the session
    await reddit.close()
    
    return posts 