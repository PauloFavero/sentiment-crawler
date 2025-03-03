from datetime import datetime
from temporalio import activity
import asyncpraw
import os
from transformers import pipeline
from typing import Dict, List

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

@activity.defn
async def analyze_sentiment(posts: List[Dict]) -> Dict:
    # Initialize the sentiment analysis pipeline
    sentiment_analyzer = pipeline(
        model="finiteautomata/bertweet-base-sentiment-analysis"
    )
    
    # Analyze sentiment for each post title
    analyzed_posts = []
    sentiment_counts = {"POS": 0, "NEG": 0, "NEU": 0}
    
    for post in posts:
        # Analyze sentiment of the title
        sentiment_result = sentiment_analyzer(post["title"])[0]
        
        # Add sentiment to post data
        analyzed_post = post.copy()
        analyzed_post["sentiment"] = sentiment_result["label"]
        analyzed_post["sentiment_score"] = sentiment_result["score"]
        analyzed_posts.append(analyzed_post)
        
        # Update sentiment counts
        sentiment_counts[sentiment_result["label"]] += 1
    
    # Calculate distribution percentages
    total_posts = len(posts)
    sentiment_distribution = {
        label: (count / total_posts) * 100 
        for label, count in sentiment_counts.items()
    }
    
    return {
        "analyzed_posts": analyzed_posts,
        "distribution": sentiment_distribution
    } 