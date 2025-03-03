import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import RedditScraperWorkflow, SentimentAnalyzerWorkflow, TwitterScraperWorkflow
from activities import scrape_reddit, analyze_sentiment, scrape_twitter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Worker starting up...")
    try:
        # Create client connected to server
        client = await Client.connect(os.getenv("TEMPORAL_HOST", "temporal:7233"))
        logger.info("Connected to Temporal server")

        # Run the worker
        worker = Worker(
            client,
            task_queue="reddit-tasks",
            workflows=[RedditScraperWorkflow, SentimentAnalyzerWorkflow, TwitterScraperWorkflow],
            activities=[scrape_reddit, analyze_sentiment, scrape_twitter]
        )
        
        # Start both workflows when the worker starts
        async def start_workflows():
            try:
                # Start the sentiment analyzer workflow first
                await client.start_workflow(
                    SentimentAnalyzerWorkflow.run,
                    id="sentiment-analyzer",
                    task_queue="reddit-tasks"
                )
                logger.info("Started sentiment analyzer workflow")
                
                # Then start the Reddit scraper workflow
                await client.start_workflow(
                    RedditScraperWorkflow.run,
                    id="reddit-scraper",
                    task_queue="reddit-tasks"
                )
                logger.info("Started Reddit scraper workflow")
                
                # Start the Twitter scraper workflow
                await client.start_workflow(
                    TwitterScraperWorkflow.run,
                    id="twitter-scraper",
                    task_queue="reddit-tasks"
                )
                logger.info("Started Twitter scraper workflow")
                
            except Exception as e:
                logger.error(f"Error starting workflows: {e}")
        
        logger.info("Starting worker...")
        # Start the workflows
        await start_workflows()
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