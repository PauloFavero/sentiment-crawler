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

@activity.defn
async def analyze_sentiment(posts: List[Dict]) -> Dict:
    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    analyzed_posts = []
    total_sentiment = 0
    
    for post in posts:
        # Check if it's a Twitter post (has 'text') or Reddit post (has 'title')
        is_twitter = 'text' in post and 'source' in post and post['source'] == 'twitter'
        content_key = 'text' if is_twitter else 'title'
        source = 'Twitter' if is_twitter else 'Reddit'
        
        # Skip if the required content field isn't available
        if content_key not in post:
            logger.warning(f"Post missing '{content_key}' field: {post}")
            continue
            
        # Create prompt for sentiment analysis
        content_to_analyze = f"""
        Title: {post['title']}
        
        Content: {post['selftext'] if post['selftext'] else 'No content'}
        
        Top Comments:
        {chr(10).join([f"- {comment['body'][:200]}..." for comment in post['comments'][:3]])}
        """
        
        prompt = f"""
        Analyze the following content from {source} and provide:
        1. A brief summary (2-3 sentences)
        2. A sentiment score between 0 and 1 where:
           - 0 is extremely negative
           - 0.5 is neutral
           - 1 is extremely positive
        
        Content: {post[content_key]}
        
        Provide your response in the following JSON format:
        {{
            "summary": "your summary here",
            "sentiment_score": 0.X,
            "reasoning": "brief explanation of the sentiment score"
        }}
        """
        
        try:
            # Get analysis from OpenAI
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a sentiment analysis expert. Provide analysis in the requested JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            analysis = response.choices[0].message.content
            # Add analysis to post data
            analyzed_post = post.copy()
            analyzed_post.update({
                "analysis": analysis,
                "sentiment_score": analysis.get("sentiment_score", 0.5)
            })
            analyzed_posts.append(analyzed_post)
            total_sentiment += analysis.get("sentiment_score", 0.5)
            
            logger.info(f"Analyzed post {post['id']} with sentiment score {analysis.get('sentiment_score', 0.5)}")
            
        except Exception as e:
            logger.error(f"Error analyzing post {post['id']}: {e}")
            # Add post with neutral sentiment if analysis fails
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

@activity.defn
async def scrape_twitter() -> list:
    """Activity that scrapes Twitter (X) for recent popular tweets."""
    # Initialize Twitter client with tweepy
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        logger.error("TWITTER_BEARER_TOKEN is not set in environment variables")
        return []
    
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
                    tweet_fields=["created_at", "public_metrics", "author_id"]
                )
            )
            
            # Process the results
            tweets = []
            
            if search_result.data:
                for tweet in search_result.data:
                    tweets.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.timestamp() if tweet.created_at else None,
                        "author_id": tweet.author_id,
                        "retweet_count": tweet.public_metrics.get("retweet_count", 0) if hasattr(tweet, "public_metrics") else 0,
                        "like_count": tweet.public_metrics.get("like_count", 0) if hasattr(tweet, "public_metrics") else 0,
                        "source": "twitter"
                    })
            
            logger.info(f"Scraped {len(tweets)} tweets from Twitter")
            return tweets
        
        except tweepy.TooManyRequests as e:
            if retry < max_retries - 1:
                # Calculate exponential backoff with jitter
                delay = (base_delay ** (retry + 1)) + (random.random() * 2)
                logger.warning(f"Twitter rate limit exceeded. Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Twitter rate limiting error after {max_retries} retries: {e}")
                return []
        except Exception as e:
            logger.error(f"Error scraping Twitter: {e}")
            return [] 