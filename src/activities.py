from temporalio import activity
import os
from openai import AsyncOpenAI
from typing import Dict
import logging
import json
from data import ScrapedData

logger = logging.getLogger(__name__)

@activity.defn
async def analyze_sentiment(scraped_data: ScrapedData) -> Dict:
    """Analyze sentiment of scraped content using OpenAI."""
    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    analyzed_posts = []
    total_sentiment = 0
    
    for content in scraped_data.items:
        # Create prompt for sentiment analysis based on content type
        content_to_analyze = ""
        
        if content.platform == "reddit":
            # Format Reddit content with title, text, and top comments
            content_to_analyze = f"""
Title: {content.title}

Content: {content.text if content.text else 'No content'}

Top Comments:
{chr(10).join([
    f"- [{reply.score} points] {reply.content[:200]}..." 
    for reply in content.replies[:3]
])}
"""
        elif content.platform == "twitter":
            # Format Twitter content with tweet and metrics
            content_to_analyze = f"""
Tweet: {content.text}

Engagement: {content.engagement_metrics.get('like_count', 0)} likes, {content.engagement_metrics.get('retweet_count', 0)} retweets
"""
        
        prompt = f"""
Analyze the following {content.platform.title()} content and its engagement. Your task has two independent parts:

PART 1: Write a brief summary (2-3 sentences) of the content and discussion.

PART 2: Determine the overall sentiment, considering both the content and responses/engagement.

For the sentiment analysis, think step by step:
1. Identify positive elements (enthusiasm, agreement, helpfulness, optimism)
2. Identify negative elements (criticism, frustration, disagreement, pessimism)
3. Identify neutral elements (factual statements, questions, balanced views)
4. Consider engagement metrics (high engagement might indicate resonance)
5. Weigh these elements to determine an overall sentiment score between 0 and 1 where:
   - 0 is extremely negative
   - 0.5 is neutral
   - 1 is extremely positive

Content to analyze:
{content_to_analyze}

Here are some examples to guide your analysis:

Example 1 (Negative):
Content: "This framework is terrible. Multiple critical bugs reported. Comments agree it's unusable."
Thinking: Strong negative language ("terrible"), technical issues mentioned, community consensus is negative, no positive aspects noted.
Sentiment score: 0.2 (quite negative)

Example 2 (Positive):
Content: "Just released v2.0! 30% performance boost, new features. Community excited, minor bugs reported."
Thinking: Announces improvements, quantified benefits, positive community response, only minor issues noted.
Sentiment score: 0.8 (quite positive)

Example 3 (Neutral):
Content: "Comparing Framework A vs B: A has better performance, B has cleaner syntax. Comments discuss trade-offs."
Thinking: Balanced comparison, no strong bias, discussion focuses on facts, valid points on both sides.
Sentiment score: 0.5 (neutral)

Provide your response in the following JSON format:
{{
    "summary": "your summary here",
    "sentiment_analysis": {{
        "positive_elements": "list key positive aspects",
        "negative_elements": "list key negative aspects",
        "neutral_elements": "list key neutral aspects",
        "engagement_impact": "how engagement affects sentiment",
        "sentiment_score": 0.X,
        "reasoning": "brief explanation of how you arrived at this score"
    }}
}}
"""
        
        try:
            # Get analysis from OpenAI
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a sentiment analysis expert. Analyze content thoroughly and provide analysis in the requested JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            try:
                analysis = json.loads(response.choices[0].message.content)
                sentiment_score = analysis["sentiment_analysis"]["sentiment_score"]
                
                # Add analysis to content data
                analyzed_content = content.model_copy(deep=True)
                analyzed_content.platform_specific_data = {
                    **(analyzed_content.platform_specific_data or {}),
                    "sentiment_analysis": analysis
                }
                
                analyzed_posts.append(analyzed_content.model_dump())
                total_sentiment += sentiment_score
                
                logger.info(f"Analyzed {content.platform} content {content.id} with sentiment score {sentiment_score}")
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing analysis JSON: {e}")
                analyzed_posts.append(content.model_dump())
                total_sentiment += 0.5
                
        except Exception as e:
            logger.error(f"Error analyzing content {content.id}: {e}")
            analyzed_posts.append(content.model_dump())
            total_sentiment += 0.5
    
    # Calculate average sentiment
    avg_sentiment = total_sentiment / len(scraped_data.items) if scraped_data.items else 0.5
    
    # Create sentiment distribution buckets
    sentiment_distribution = {
        "positive": len([p for p in analyzed_posts if p.get("platform_specific_data", {}).get("sentiment_analysis", {}).get("sentiment_score", 0.5) > 0.6]),
        "neutral": len([p for p in analyzed_posts if 0.4 <= p.get("platform_specific_data", {}).get("sentiment_analysis", {}).get("sentiment_score", 0.5) <= 0.6]),
        "negative": len([p for p in analyzed_posts if p.get("platform_specific_data", {}).get("sentiment_analysis", {}).get("sentiment_score", 0.5) < 0.4])
    }
    
    return {
        "analyzed_posts": analyzed_posts,
        "distribution": sentiment_distribution,
        "average_sentiment": avg_sentiment,
        "platform": scraped_data.platform,
        "metadata": {
            "original_metadata": scraped_data.metadata,
            "analysis_timestamp": scraped_data.timestamp
        }
    }
