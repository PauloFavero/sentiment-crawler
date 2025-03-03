import gspread
import os
import json
import logging
import traceback
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class SheetsClient:
    def __init__(self):
        # Load credentials from environment variable
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable not set")
        
        try:
            # Parse credentials from environment variable
            creds_info = json.loads(creds_json)
            self.sheet_id = os.getenv("GOOGLE_SHEET_ID")
            if not self.sheet_id:
                raise ValueError("GOOGLE_SHEET_ID environment variable not set")
            
            # Set up credentials
            scope = ["https://spreadsheets.google.com/feeds", 
                     "https://www.googleapis.com/auth/drive"]
            
            # Create credentials from the parsed JSON
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
            
            # Authorize with gspread
            self.client = gspread.authorize(credentials)
            
            logger.info("Successfully initialized Google Sheets client")
        except Exception as e:
            logger.error(f"Error initializing Google Sheets client: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def append_sentiment_results(self, results: Dict[str, Any]) -> bool:
        """
        Append sentiment analysis results to the Google Sheet.
        
        Args:
            results: Dictionary containing sentiment analysis results
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Open the sheet
            logger.info(f"Attempting to open sheet with ID: {self.sheet_id}")
            sheet = self.client.open_by_key(self.sheet_id).sheet1
            logger.info(f"Successfully opened Google Sheet")
            
            # Get the timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log the structure of the results for debugging
            logger.info(f"Results structure: {json.dumps(results, default=str)[:200]}...")
            
            # For each post in the results
            for post in results.get("analyzed_posts", []):
                logger.info(f"Processing post: {post.get('id', 'unknown')}")
                
                # Prepare row data
                source = post.get("platform", "unknown")
                content = post.get("title", post.get("text", "No content"))
                
                # Extract sentiment score from the platform_specific_data field
                platform_specific_data = post.get("platform_specific_data", {})
                logger.info(f"Platform specific data: {json.dumps(platform_specific_data, default=str)}")
                
                # Try both potential locations for sentiment score
                sentiment_score = 0
                # Try first directly from the post
                if "sentiment_score" in post:
                    sentiment_score = post.get("sentiment_score", 0)
                    logger.info(f"Found sentiment score directly in post: {sentiment_score}")
                
                # If not found, try in platform_specific_data.sentiment_analysis
                if sentiment_score == 0 and platform_specific_data:
                    sentiment_analysis = platform_specific_data.get("sentiment_analysis", {})
                    
                    # If sentiment_analysis is a dictionary and has 'sentiment_score'
                    if isinstance(sentiment_analysis, dict) and "sentiment_score" in sentiment_analysis:
                        sentiment_score = sentiment_analysis.get("sentiment_score", 0)
                        logger.info(f"Found sentiment score in sentiment_analysis: {sentiment_score}")
                    
                    # If sentiment_analysis is a dictionary and has nested 'sentiment_analysis' with 'sentiment_score'
                    elif isinstance(sentiment_analysis, dict) and "sentiment_analysis" in sentiment_analysis:
                        nested_analysis = sentiment_analysis.get("sentiment_analysis", {})
                        if isinstance(nested_analysis, dict) and "sentiment_score" in nested_analysis:
                            sentiment_score = nested_analysis.get("sentiment_score", 0)
                            logger.info(f"Found sentiment score in nested sentiment_analysis: {sentiment_score}")
                
                logger.info(f"Final extracted sentiment score: {sentiment_score} from post {post.get('id', 'unknown')}")
                
                summary = "No summary available"
                
                # Try to extract summary from the analysis
                try:
                    if isinstance(sentiment_analysis, dict):
                        # Try direct access first
                        if "summary" in sentiment_analysis:
                            summary = sentiment_analysis.get("summary", "No summary available")
                            logger.info(f"Found summary directly in sentiment_analysis")
                        # Try nested access
                        elif "sentiment_analysis" in sentiment_analysis and isinstance(sentiment_analysis.get("sentiment_analysis"), dict):
                            nested_analysis = sentiment_analysis.get("sentiment_analysis", {})
                            if "summary" in nested_analysis:
                                summary = nested_analysis.get("summary", "No summary available")
                                logger.info(f"Found summary in nested sentiment_analysis")
                except Exception as e:
                    logger.warning(f"Could not parse analysis data: {e}")
                    summary = "Error parsing analysis"
                
                # Prepare the row to append
                row = [timestamp, source, 
                       (content[:100] + "...") if content else "No content", 
                       sentiment_score, summary]
                logger.info(f"Appending row: {row}")
                sheet.append_row(row)
                logger.info(f"Successfully appended row for post {post.get('id', 'unknown')}")
            
            # Also add the overall sentiment
            row = [
                timestamp,
                "SUMMARY",
                f"Distribution: pos={results.get('distribution', {}).get('positive', 0)}, " +
                f"neu={results.get('distribution', {}).get('neutral', 0)}, " +
                f"neg={results.get('distribution', {}).get('negative', 0)}",
                results.get("average_sentiment", 0),
                "Average sentiment score"
            ]
            logger.info(f"Appending summary row: {row}")
            sheet.append_row(row)
            
            logger.info(f"Successfully appended {len(results.get('analyzed_posts', []))} rows to Google Sheet")
            return True
        except Exception as e:
            logger.error(f"Error appending to Google Sheet: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False 