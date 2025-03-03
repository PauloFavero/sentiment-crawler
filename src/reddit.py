from datetime import datetime
from temporalio import activity
import asyncpraw
import os
from openai import AsyncOpenAI
from typing import Dict, List
import logging
import tweepy
import asyncio
import random

logger = logging.getLogger(__name__)


@activity.defn
async def scrape_reddit() -> list:
    # Initialize Reddit client with asyncpraw
    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="my_reddit_scraper/1.0"
    )
    
    subreddit = await reddit.subreddit("programming")
    posts = []
    
    try:
        # Get hot posts
        async for submission in subreddit.hot(limit=10):
            # Create post data structure
            post_data = {
                "id": submission.id,
                "title": submission.title,
                "score": submission.score,
                "url": submission.url,
                "created_utc": submission.created_utc,
                "selftext": submission.selftext,
                "num_comments": submission.num_comments,
                "comments": []
            }
            
            # Fetch comments for the submission
            submission.comment_sort = "top"  # Sort comments by top
            await submission.load()  # Ensure all comments are loaded
            
            # Get top-level comments
            submission.comments.replace_more(limit=0)  # Remove "load more comments" objects
            
            async for top_comment in submission.comments:
                if not top_comment.stickied:  # Skip stickied comments
                    comment_data = {
                        "id": top_comment.id,
                        "body": top_comment.body,
                        "score": top_comment.score,
                        "created_utc": top_comment.created_utc,
                        "author": str(top_comment.author) if top_comment.author else "[deleted]",
                        "replies": []
                    }
                    
                    # Get second-level replies
                    if hasattr(top_comment, "replies"):
                        for reply in top_comment.replies[:5]:  # Limit to first 5 replies
                            if hasattr(reply, "body"):  # Check if it's a valid comment
                                reply_data = {
                                    "id": reply.id,
                                    "body": reply.body,
                                    "score": reply.score,
                                    "created_utc": reply.created_utc,
                                    "author": str(reply.author) if reply.author else "[deleted]"
                                }
                                comment_data["replies"].append(reply_data)
                    
                    post_data["comments"].append(comment_data)
            
            posts.append(post_data)
            logger.info(f"Scraped post {submission.id} with {len(post_data['comments'])} comments")
    
    except Exception as e:
        logger.error(f"Error scraping Reddit: {e}")
        raise
    
    finally:
        # Close the session
        await reddit.close()
    
    logger.info(f"Successfully scraped {len(posts)} posts with comments")
    return posts
