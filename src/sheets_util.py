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
            
            # Handle the case where results is a list (from the new structure)
            if isinstance(results, list):
                for result_item in results:
                    self._process_result_item(result_item, sheet, timestamp)
            else:
                # Handle the original case where results is a dictionary
                self._process_result_item(results, sheet, timestamp)
            
            logger.info(f"Successfully appended rows to Google Sheet")
            return True
        except Exception as e:
            logger.error(f"Error appending to Google Sheet: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _process_result_item(self, result_item: Dict[str, Any], sheet, timestamp: str) -> None:
        """
        Process a single result item and append its data to the sheet.
        
        Args:
            result_item: Dictionary containing sentiment analysis results
            sheet: Google Sheet to append to
            timestamp: Timestamp string
        """
        # For each post in the results
        for post in result_item.get("analyzed_posts", []):
            logger.info(f"Processing post: {post.get('id', 'unknown')}")
            
            # Prepare row data
            source = post.get("platform", "unknown")
            content = post.get("title", post.get("text", "No content"))
            
            # Extract sentiment score and summary from platform_specific_data
            platform_specific_data = post.get("platform_specific_data", {})
            sentiment_analysis = platform_specific_data.get("sentiment_analysis", {})
            
            # Get sentiment score
            sentiment_score = sentiment_analysis.get("sentiment_score", 0)
            logger.info(f"Extracted sentiment score: {sentiment_score} from post {post.get('id', 'unknown')}")
            
            # Get summary
            summary = platform_specific_data.get("summary", "No summary available")
            
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
            f"Distribution: pos={result_item.get('distribution', {}).get('positive', 0)}, " +
            f"neu={result_item.get('distribution', {}).get('neutral', 0)}, " +
            f"neg={result_item.get('distribution', {}).get('negative', 0)}",
            result_item.get("average_sentiment", 0),
            "Average sentiment score"
        ]
        logger.info(f"Appending summary row: {row}")
        sheet.append_row(row) 