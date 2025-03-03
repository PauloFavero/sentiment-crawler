import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import RedditScraperWorkflow
from activities import scrape_reddit, analyze_sentiment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Worker starting up...")
    try:
        # Create client connected to server at the given address
        client = await Client.connect(os.getenv("TEMPORAL_HOST", "temporal:7233"))
        logger.info("Connected to Temporal server")

        # Run the worker
        worker = Worker(
            client,
            task_queue="reddit-tasks",
            workflows=[RedditScraperWorkflow],
            activities=[scrape_reddit, analyze_sentiment]
        )
        
        # Start the Reddit scraper workflow when the worker starts
        async def start_reddit_scraper():
            try:
                logger.info("Starting Reddit scraper workflow...")
                await client.start_workflow(
                    RedditScraperWorkflow.run,
                    id="reddit-scraper-initial",
                    task_queue="reddit-tasks"
                )
                logger.info("Reddit scraper workflow started successfully")
            except Exception as e:
                logger.error(f"Error starting Reddit scraper workflow: {e}")
        
        logger.info("Starting worker...")
        # Start the Reddit scraper workflow
        await start_reddit_scraper()
        # Run the worker
        await worker.run()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 