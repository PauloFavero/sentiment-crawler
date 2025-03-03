from temporalio import activity
import asyncpraw
import os
from typing import List
import logging
from data import ScrapedData, Content, Author, Reply

logger = logging.getLogger(__name__)


@activity.defn
async def scrape_reddit() -> ScrapedData:
    # Initialize Reddit client with asyncpraw
    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="my_reddit_scraper/1.0"
    )
    
    subreddit = await reddit.subreddit("programming")
    contents: List[Content] = []
    
    try:
        # Get hot posts
        async for submission in subreddit.hot(limit=3):
            # Create author - handle deleted/None authors safely
            author_name = "[deleted]"
            author_id = "deleted"
            is_mod = False
            
            if submission.author:
                try:
                    author_name = str(submission.author.name)
                    # Use name as id if actual id is not available
                    author_id = str(submission.author.name)
                    is_mod = bool(submission.author.is_mod) if hasattr(submission.author, "is_mod") else False
                except Exception as e:
                    logger.warning(f"Error fetching author details: {e}")
            
            author = Author(
                id=author_id,
                name=author_name,
                platform_specific_data={"is_mod": is_mod} if is_mod else None
            )
            
            # Process comments
            replies: List[Reply] = []
            
            # Fetch comments
            submission.comment_sort = "top"  # Sort comments by top
            await submission.load()  # Ensure all comments are loaded
            
            # Get top-level comments
            submission.comments.replace_more(limit=0)  # Remove "load more comments" objects
            
            async for top_comment in submission.comments:
                if not top_comment.stickied:  # Skip stickied comments
                    # Handle comment author similarly
                    comment_author_name = "[deleted]"
                    comment_author_id = "deleted"
                    
                    if top_comment.author:
                        try:
                            comment_author_name = str(top_comment.author.name)
                            comment_author_id = str(top_comment.author.name)
                        except Exception as e:
                            logger.warning(f"Error fetching comment author details: {e}")
                    
                    comment_author = Author(
                        id=comment_author_id,
                        name=comment_author_name
                    )
                    
                    reply = Reply(
                        id=top_comment.id,
                        content=top_comment.body,
                        author=comment_author,
                        score=top_comment.score,
                        created_at=top_comment.created_utc,
                        platform="reddit",
                        platform_specific_data={
                            "is_stickied": top_comment.stickied,
                            "is_edited": bool(top_comment.edited) if hasattr(top_comment, "edited") else False
                        }
                    )
                    
                    replies.append(reply)
            
            # Create content
            content = Content(
                id=submission.id,
                title=submission.title,
                text=submission.selftext,
                author=author,
                created_at=submission.created_utc,
                score=submission.score,
                url=submission.url,
                platform="reddit",
                engagement_metrics={
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio if hasattr(submission, "upvote_ratio") else None,
                    "num_comments": submission.num_comments
                },
                replies=replies[:10],  # Limit to top 10 comments
                platform_specific_data={
                    "is_self": submission.is_self,
                    "over_18": submission.over_18,
                    "spoiler": submission.spoiler if hasattr(submission, "spoiler") else False
                }
            )
            
            contents.append(content)
            logger.info(f"Scraped Reddit post {submission.id} with {len(replies)} comments")
    
    except Exception as e:
        logger.error(f"Error scraping Reddit: {e}")
        raise
    
    finally:
        # Close the session
        await reddit.close()
    
    scraped_data = ScrapedData(
        platform="reddit",
        items=contents,
        metadata={
            "subreddit": "programming",
            "sort": "hot"
        }
    )
    
    logger.info(f"Successfully scraped {len(contents)} Reddit posts")
    return scraped_data
