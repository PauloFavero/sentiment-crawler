from temporalio import activity
import os
from openai import AsyncOpenAI
from typing import Dict
import logging
import json
from data import ScrapedData
from prompt import create_sentiment_analysis_prompt

logger = logging.getLogger(__name__)

@activity.defn
async def analyze_sentiment(scraped_data: ScrapedData) -> Dict:
    """Analyze sentiment of scraped content using OpenAI."""
    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    analyzed_posts = []
    total_sentiment = 0
    
    for content in scraped_data.items:
        # Create prompt for sentiment analysis
        prompt = create_sentiment_analysis_prompt(content)
        
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
            try:
                analysis = json.loads(response.choices[0].message.content)
                sentiment_score = analysis["sentiment_analysis"]["sentiment_score"]
                
                # Add analysis to content data
                analyzed_content = content.model_copy(deep=True)
                if analyzed_content.platform_specific_data is None:
                    analyzed_content.platform_specific_data = {}
                analyzed_content.platform_specific_data["sentiment_analysis"] = analysis
                
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