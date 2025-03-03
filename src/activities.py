from temporalio import activity
import os
from openai import AsyncOpenAI
from typing import Dict, List
import logging
from .types import Post

logger = logging.getLogger(__name__)

@activity.defn
async def analyze_sentiment(posts: List[Post]) -> Dict:
    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    analyzed_posts = []
    total_sentiment = 0
    
    for post in posts:
        # Create source-specific prompt
        if post.source == "reddit":
            content_to_analyze = f"""
            Title: {post.title}
            
            Content: {post.selftext if post.selftext else 'No content'}
            
            Top Comments:
            {chr(10).join([f"- {comment.content[:200]}..." for comment in post.comments[:3]])}
            """
        else:  # Twitter
            content_to_analyze = f"""
            Tweet: {post.content}
            
            Engagement: {post.get_engagement_score()} (likes + retweets)
            """
        
        prompt = f"""
        Analyze the following {post.source} post. Your task has two independent parts:
        
        PART 1: Write a brief summary (2-3 sentences) of the content.
        
        PART 2: Determine the overall sentiment, considering:
        - Content tone and language
        - User engagement ({post.get_engagement_score()} interactions)
        {f'- Community response ({len(post.comments)} comments)' if post.source == 'reddit' else ''}
        
        {content_to_analyze}
        
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
