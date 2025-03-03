import gspread
import os
import json
import logging
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
            sheet = self.client.open_by_key(self.sheet_id).sheet1
            
            # Get the timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # For each post in the results
            for post in results.get("analyzed_posts", []):
                # Prepare row data
                source = post.get("source", "unknown")
                content = post.get("title", post.get("text", "No content"))
                sentiment_score = post.get("sentiment_score", 0)
                summary = "No summary available"
                
                # Try to extract summary from the analysis
                try:
                    if isinstance(post.get("analysis"), str):
                        import json
                        analysis_data = json.loads(post.get("analysis"))
                        summary = analysis_data.get("summary", "No summary available")
                    elif isinstance(post.get("analysis"), dict):
                        summary = post.get("analysis", {}).get("summary", "No summary available")
                except Exception as e:
                    logger.warning(f"Could not parse analysis data: {e}")
                
                # Prepare the row to append
                row = [timestamp, source, content[:100] + "...", sentiment_score, summary]
                sheet.append_row(row)
            
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
            sheet.append_row(row)
            
            logger.info(f"Successfully appended {len(results.get('analyzed_posts', []))} rows to Google Sheet")
            return True
        except Exception as e:
            logger.error(f"Error appending to Google Sheet: {e}")
            return False 