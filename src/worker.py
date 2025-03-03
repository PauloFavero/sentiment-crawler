import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import GreetingWorkflow, RedditScraperWorkflow
from activities import say_hello, scrape_reddit

async def main():
    # Create client connected to server at the given address
    client = await Client.connect(os.getenv("TEMPORAL_HOST", "temporal:7233"))

    # Run the worker
    worker = Worker(
        client,
        task_queue="reddit-tasks",
        workflows=[GreetingWorkflow, RedditScraperWorkflow],
        activities=[say_hello, scrape_reddit]
    )
    
    # Start the Reddit scraper workflow when the worker starts
    async def start_reddit_scraper():
        try:
            await client.start_workflow(
                RedditScraperWorkflow.run,
                id="reddit-scraper-initial",
                task_queue="reddit-tasks"
            )
        except Exception as e:
            print(f"Error starting Reddit scraper workflow: {e}")
    
    print("Starting worker...")
    # Start the Reddit scraper workflow
    await start_reddit_scraper()
    # Run the worker
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 