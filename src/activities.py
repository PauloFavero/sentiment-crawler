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
        # Create prompt for sentiment analysis
        content_to_analyze = f"""
        Title: {post['title']}
        
        Content: {post['selftext'] if post['selftext'] else 'No content'}
        
        Top Comments:
        {chr(10).join([f"- {comment['body'][:200]}..." for comment in post['comments'][:3]])}
        """
        
        prompt = f"""
        Analyze the following Reddit post and its top comments and provide:
        1. A brief summary (2-3 sentences)
        2. A sentiment score between 0 and 1 where:
           - 0 is extremely negative
           - 0.5 is neutral
           - 1 is extremely positive
        
        {content_to_analyze}
        
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