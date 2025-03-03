from temporalio import activity
import os
from openai import AsyncOpenAI
from typing import Dict, List
import logging
from models import Post
from sheets_util import SheetsClient
from datetime import datetime

logger = logging.getLogger(__name__)

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
        Analyze the following {source} post and its top comments. Your task has two independent parts:
        
        PART 1: Write a brief summary (2-3 sentences) of the post and discussion.
        
        PART 2: Determine the overall sentiment of the entire content (title, post content, and comments combined).
        
        For the sentiment analysis, think step by step:
        1. Identify positive elements (enthusiasm, agreement, helpfulness, optimism)
        2. Identify negative elements (criticism, frustration, disagreement, pessimism)
        3. Identify neutral elements (factual statements, questions, balanced views)
        4. Weigh these elements to determine an overall sentiment score between 0 and 1 where:
           - 0 is extremely negative
           - 0.5 is neutral
           - 1 is extremely positive
        
        Content: {post[content_key]}
        
        Here are some examples of how to analyze sentiment:
        
        Example 1:
        Content: "This new framework is terrible. It's slow, buggy, and poorly documented. Most comments agree it's a waste of time."
        Thinking: The post expresses strong negative opinions about a framework. Words like "terrible", "slow", "buggy" indicate frustration. Comments reinforce this negative view. No significant positive elements.
        Sentiment score: 0.2 (quite negative)
        
        Example 2:
        Content: "Just released v2.0 of my open-source tool. It has 30% better performance and new features. Comments are mostly excited, though some mention minor bugs."
        Thinking: The post announces positive improvements. Words like "better performance" and "new features" show progress. Comments are "mostly excited" (positive) with only "minor bugs" mentioned (slight negative).
        Sentiment score: 0.8 (quite positive)
        
        Example 3:
        Content: "Comparing Rust vs Go for backend development. Both have strengths: Rust for performance, Go for simplicity. Comments debate trade-offs with valid points on both sides."
        Thinking: The post presents a balanced comparison. No strong positive or negative language. Comments show debate but with "valid points on both sides" suggesting a balanced discussion.
        Sentiment score: 0.5 (neutral)
        
        Provide your response in the following JSON format:
        {{
            "summary": "your summary here",
            "sentiment_analysis": {{
                "positive_elements": "list key positive aspects",
                "negative_elements": "list key negative aspects",
                "neutral_elements": "list key neutral aspects",
                "sentiment_score": 0.X,
                "reasoning": "brief explanation of how you arrived at this score"
            }}
        }}
        """
        
        try:
            # Get analysis from OpenAI
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a sentiment analysis expert. Analyze content thoroughly and provide analysis in the requested JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            analysis = response.choices[0].message.content
            # Add analysis to post data
            analyzed_post = post.copy()
            
            # Extract sentiment score from the nested structure
            sentiment_score = 0.5  # Default
            try:
                import json
                parsed_analysis = json.loads(analysis)
                sentiment_score = parsed_analysis.get("sentiment_analysis", {}).get("sentiment_score", 0.5)
            except Exception as e:
                logger.error(f"Error parsing analysis JSON: {e}")
            
            analyzed_post.update({
                "analysis": analysis,
                "sentiment_score": sentiment_score
            })
            analyzed_posts.append(analyzed_post)
            total_sentiment += sentiment_score
            
            logger.info(f"Analyzed post {post['id']} with sentiment score {sentiment_score}")
            
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
async def store_results_in_sheets(sentiment_results: Dict) -> bool:
    """
    Activity to store sentiment analysis results in Google Sheets.
    
    Args:
        sentiment_results: Dictionary containing sentiment analysis results
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize the Google Sheets client
        sheets_client = SheetsClient()
        
        # Store the results
        success = sheets_client.append_sentiment_results(sentiment_results)
        
        if success:
            logger.info("Successfully stored sentiment results in Google Sheets")
        else:
            logger.error("Failed to store sentiment results in Google Sheets")
            
        return success
    except Exception as e:
        logger.error(f"Error storing sentiment results in Google Sheets: {e}")
        return False
