#!/usr/bin/env python
import logging
import os
import sys
import json
import traceback
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

# Add the current directory to the Python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
def load_env_vars():
    try:
        # Find the .env file in the project root (parent of the src directory)
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            logger.info(f"Loading environment variables from {env_path}")
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"\'')
            return True
        else:
            logger.error(f".env file not found at {env_path}")
            return False
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
        return False

# Import SheetsClient from the current directory
try:
    from sheets_util import SheetsClient
except ImportError as e:
    logger.error(f"Could not import SheetsClient: {e}")
    logger.error("Make sure you're running this from the src directory.")
    sys.exit(1)

def create_sample_data() -> Dict[str, Any]:
    """Create sample sentiment analysis results for testing"""
    return {
        "analyzed_posts": [
            {
                "id": "test_post_1",
                "title": "Test Post Title",
                "text": "This is a test post content.",
                "source": "reddit",
                "sentiment_score": 0.75,
                "analysis": "Positive sentiment about testing"
            },
            {
                "id": "test_post_2",
                "title": "Another Test Post",
                "text": "This is another test post with negative content.",
                "source": "twitter",
                "sentiment_score": -0.3,
                "analysis": "Negative sentiment about testing"
            }
        ],
        "distribution": {
            "positive": 1,
            "neutral": 0,
            "negative": 1
        },
        "average_sentiment": 0.225
    }

def test_sheets_integration():
    """Test the Google Sheets integration"""
    logger.info("Starting Google Sheets integration test")
    
    # Print all environment variables (redacted for security)
    env_vars = ""
    for key, value in os.environ.items():
        if "KEY" in key or "SECRET" in key or "CREDENTIALS" in key:
            value = "[REDACTED]"
        env_vars += f"{key}={value[:10]}...\n"
    
    logger.info(f"Environment variables: \n{env_vars}")
    
    # Check if the environment variables are set
    if not os.getenv("GOOGLE_CREDENTIALS_JSON") or not os.getenv("GOOGLE_SHEET_ID"):
        logger.error("Google Sheets credentials not found in environment variables")
        logger.info("Make sure GOOGLE_CREDENTIALS_JSON and GOOGLE_SHEET_ID are set")
        return False
    
    try:
        # Initialize the Google Sheets client
        logger.info("Initializing Google Sheets client")
        sheets_client = SheetsClient()
        
        # Create sample data
        logger.info("Creating sample sentiment analysis data")
        sample_data = create_sample_data()
        
        # Store the sample data in Google Sheets
        logger.info("Attempting to store data in Google Sheets")
        success = sheets_client.append_sentiment_results(sample_data)
        
        if success:
            logger.info("✅ Successfully stored test data in Google Sheets!")
            logger.info(f"Check your sheet with ID: {os.getenv('GOOGLE_SHEET_ID')}")
            return True
        else:
            logger.error("❌ Failed to store test data in Google Sheets")
            return False
    
    except Exception as e:
        logger.error(f"Error during Google Sheets test: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🧪 GOOGLE SHEETS INTEGRATION TEST")
    print("="*50 + "\n")
    
    # Load environment variables before testing
    env_loaded = load_env_vars()
    if not env_loaded:
        print("⚠️ Warning: Could not load environment variables from .env file")
        print("⚠️ The test will use existing environment variables if available")
    
    result = test_sheets_integration()
    
    print("\n" + "="*50)
    if result:
        print("✅ TEST PASSED: Google Sheets integration is working!")
    else:
        print("❌ TEST FAILED: Could not store data in Google Sheets")
    print("="*50 + "\n")
    
    sys.exit(0 if result else 1) 