from temporalio import activity
import os
import logging
import tweepy
import asyncio
import random

logger = logging.getLogger(__name__)
@activity.defn
async def scrape_twitter() -> list:

	"""Activity that scrapes Twitter (X) for recent popular tweets."""
	# Initialize Twitter client with tweepy
	bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
	if not bearer_token:
			logger.error("TWITTER_BEARER_TOKEN is not set in environment variables")
			return []
	
	# Create a client instance
	client = tweepy.Client(bearer_token=bearer_token)
	
	# Since tweepy is synchronous, we'll run it in an executor
	loop = asyncio.get_event_loop()
	
	# Define search parameters - looking for technology-related tweets
	query = "tech OR programming OR AI OR technology OR software"
	
	# Implement retry logic with exponential backoff
	max_retries = 3
	base_delay = 2  # seconds
	
	for retry in range(max_retries):
			try:
					# Execute the search using an executor to avoid blocking
					search_result = await loop.run_in_executor(
							None, 
							lambda: client.search_recent_tweets(
									query=query,
									max_results=10,
									tweet_fields=["created_at", "public_metrics", "author_id"]
							)
					)
					
					# Process the results
					tweets = []
					
					if search_result.data:
							for tweet in search_result.data:
									tweets.append({
											"id": tweet.id,
											"text": tweet.text,
											"created_at": tweet.created_at.timestamp() if tweet.created_at else None,
											"author_id": tweet.author_id,
											"retweet_count": tweet.public_metrics.get("retweet_count", 0) if hasattr(tweet, "public_metrics") else 0,
											"like_count": tweet.public_metrics.get("like_count", 0) if hasattr(tweet, "public_metrics") else 0,
											"source": "twitter"
									})
					
					logger.info(f"Scraped {len(tweets)} tweets from Twitter")
					return tweets
			
			except tweepy.TooManyRequests as e:
					if retry < max_retries - 1:
							# Calculate exponential backoff with jitter
							delay = (base_delay ** (retry + 1)) + (random.random() * 2)
							logger.warning(f"Twitter rate limit exceeded. Retrying in {delay:.2f} seconds...")
							await asyncio.sleep(delay)
					else:
							logger.error(f"Twitter rate limiting error after {max_retries} retries: {e}")
							return []
			except Exception as e:
					logger.error(f"Error scraping Twitter: {e}")
					return [] 