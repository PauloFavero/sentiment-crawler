from datetime import datetime
from temporalio import activity
import asyncpraw
import os
from openai import AsyncOpenAI
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


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
    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    analyzed_posts = []
    total_sentiment = 0
    
    for post in posts:
        # Create prompt for sentiment analysis
        prompt = f"""
        Analyze the following title from Reddit and provide:
        1. A brief summary (2-3 sentences)
        2. A sentiment score between 0 and 1 where:
           - 0 is extremely negative
           - 0.5 is neutral
           - 1 is extremely positive
        
        Title: {post['title']}
        
        Provide your response in the following JSON format:
        {{
            "summary": "your summary here",
            "sentiment_score": 0.X
        }}
        """
        
        # Get analysis from OpenAI
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a sentiment analysis expert. Provide analysis in the requested JSON format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        try:
            analysis = response.choices[0].message.content
            # Add analysis to post data
            analyzed_post = post.copy()
            analyzed_post.update({
                "analysis": analysis,
                "sentiment_score": analysis.get("sentiment_score", 0.5)
            })
            analyzed_posts.append(analyzed_post)
            total_sentiment += analysis.get("sentiment_score", 0.5)
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            # Add post with neutral sentiment if parsing fails
            analyzed_posts.append({**post, "sentiment_score": 0.5})
            total_sentiment += 0.5
    
    # Calculate average sentiment
    avg_sentiment = total_sentiment / len(posts) if posts else 0.5
    
    # Create sentiment distribution buckets
    sentiment_distribution = {
        "positive": len([p for p in analyzed_posts if p["sentiment_score"] > 0.6]),
        "neutral": len([p for p in analyzed_posts if 0.4 <= p["sentiment_score"] <= 0.6]),
        "negative": len([p for p in analyzed_posts if p["sentiment_score"] < 0.4])
    }
    
    return {
        "analyzed_posts": analyzed_posts,
        "distribution": sentiment_distribution,
        "average_sentiment": avg_sentiment
    } 