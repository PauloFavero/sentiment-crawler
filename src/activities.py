from temporalio import activity
import os
from openai import AsyncOpenAI
from typing import Dict
import logging
import json
from data import ScrapedData
from prompt import create_sentiment_analysis_prompt
from sheets_util import SheetsClient

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
                # Parse the LLM response and extract sentiment analysis
                sentiment_data = json.loads(response.choices[0].message.content)
                
                # Update the content object with sentiment analysis results
                content_dict = content.model_dump()
                if "platform_specific_data" not in content_dict:
                    content_dict["platform_specific_data"] = {}
                
                content_dict["platform_specific_data"]["sentiment_analysis"] = sentiment_data["sentiment_analysis"]
                content_dict["platform_specific_data"]["summary"] = sentiment_data["summary"]
                
                # Add to analyzed posts and update total sentiment
                analyzed_posts.append(content_dict)
                total_sentiment += sentiment_data["sentiment_analysis"]["sentiment_score"]
                
                logger.info(f"Analyzed {content.platform} content {content.id} with sentiment score {sentiment_data['sentiment_analysis']['sentiment_score']}")
                
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
