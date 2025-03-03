from temporalio import activity
import os
from typing import List
import logging
import tweepy
import asyncio
import random
from data import ScrapedData, Content, Author

logger = logging.getLogger(__name__)

@activity.defn
async def scrape_twitter() -> ScrapedData:
    """Activity that scrapes Twitter (X) for recent popular tweets."""
    # Initialize Twitter client with tweepy
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        logger.error("TWITTER_BEARER_TOKEN is not set in environment variables")
        return ScrapedData(platform="twitter", items=[])
    
    # Create a client instance
    client = tweepy.Client(bearer_token=bearer_token)
    
    # Since tweepy is synchronous, we'll run it in an executor
    loop = asyncio.get_event_loop()
    
    # Define search parameters - looking for technology-related tweets
    query = "tech OR programming OR AI OR technology OR software"
    
    # Implement retry logic with exponential backoff
    max_retries = 3
    base_delay = 2  # seconds
    
    for retry in range(max_retries):
        try:
            # Execute the search using an executor to avoid blocking
            search_result = await loop.run_in_executor(
                None, 
                lambda: client.search_recent_tweets(
                    query=query,
                    max_results=10,
                    tweet_fields=["created_at", "public_metrics", "author_id", "conversation_id"],
                    expansions=["author_id", "referenced_tweets.id"],
                    user_fields=["username", "name"]
                )
            )
            
            contents: List[Content] = []
            
            if search_result.data:
                # Create user lookup dict
                users = {user.id: user for user in search_result.includes.get("users", [])}
                
                for tweet in search_result.data:
                    # Get author info
                    user = users.get(tweet.author_id)
                    author = Author(
                        id=str(tweet.author_id),
                        name=user.username if user else str(tweet.author_id),
                        platform_specific_data={
                            "display_name": user.name if user else None
                        }
                    )
                    
                    # Create content
                    content = Content(
                        id=str(tweet.id),
                        text=tweet.text,
                        author=author,
                        created_at=tweet.created_at.timestamp(),
                        platform="twitter",
                        engagement_metrics={
                            "retweet_count": tweet.public_metrics.get("retweet_count", 0),
                            "like_count": tweet.public_metrics.get("like_count", 0),
                            "reply_count": tweet.public_metrics.get("reply_count", 0),
                            "quote_count": tweet.public_metrics.get("quote_count", 0)
                        },
                        platform_specific_data={
                            "conversation_id": tweet.conversation_id,
                            "referenced_tweets": [
                                {"type": ref.type, "id": ref.id}
                                for ref in tweet.referenced_tweets
                            ] if tweet.referenced_tweets else None
                        }
                    )
                    
                    contents.append(content)
            
            scraped_data = ScrapedData(
                platform="twitter",
                items=contents,
                metadata={
                    "query": query,
                    "search_type": "recent"
                }
            )
            
            logger.info(f"Scraped {len(contents)} tweets from Twitter")
            return scraped_data
        
        except tweepy.TooManyRequests as e:
            if retry < max_retries - 1:
                # Calculate exponential backoff with jitter
                delay = (base_delay ** (retry + 1)) + (random.random() * 2)
                logger.warning(f"Twitter rate limit exceeded. Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Twitter rate limiting error after {max_retries} retries: {e}")
                return ScrapedData(platform="twitter", items=[])
        except Exception as e:
            logger.error(f"Error scraping Twitter: {e}")
            return ScrapedData(platform="twitter", items=[]) 