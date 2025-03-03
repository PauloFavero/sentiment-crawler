#!/usr/bin/env python
import os
import json
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_google_credentials():
    """Check if Google Sheets credentials are properly configured"""
    print("\n" + "="*50)
    print("🔍 CHECKING GOOGLE SHEETS CREDENTIALS")
    print("="*50)
    
    # Check if environment variables are set
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not creds_json:
        print("❌ GOOGLE_CREDENTIALS_JSON environment variable is not set")
        return False
    
    if not sheet_id:
        print("❌ GOOGLE_SHEET_ID environment variable is not set")
        return False
    
    print("✅ Environment variables are set")
    
    # Parse credentials JSON
    try:
        creds_info = json.loads(creds_json)
        service_account_email = creds_info.get("client_email")
        
        if not service_account_email:
            print("❌ Could not find client_email in credentials JSON")
            return False
        
        print(f"✅ Successfully parsed credentials JSON")
        print(f"✅ Service account email: {service_account_email}")
        
        # Print instructions for sharing the sheet
        print("\n" + "="*50)
        print("📋 HOW TO FIX PERMISSIONS")
        print("="*50)
        print(f"1. Open your Google Sheet with ID: {sheet_id}")
        print(f"2. Click the 'Share' button in the top-right corner")
        print(f"3. Enter the service account email: {service_account_email}")
        print(f"4. Give 'Editor' access")
        print(f"5. Uncheck 'Notify people'")
        print(f"6. Click 'Share'")
        print("\nOnce you've done this, run the test script again with:")
        print("docker exec -it hackathon /bin/bash -c \"cd /app && python src/test_sheets.py\"")
        
        return True
    except json.JSONDecodeError:
        print("❌ Could not parse GOOGLE_CREDENTIALS_JSON as valid JSON")
        return False
    except Exception as e:
        print(f"❌ Error checking credentials: {e}")
        return False

if __name__ == "__main__":
    check_google_credentials() 