from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict
from data import ScrapedData

with workflow.unsafe.imports_passed_through():
    from activities import analyze_sentiment
    from reddit import scrape_reddit
    from twitter import scrape_twitter

@workflow.defn
class RedditScraperWorkflow:
    @workflow.run
    async def run(self) -> None:
        # Get the handle to the sentiment analyzer workflow (no await needed)
        sentiment_analyzer = workflow.get_external_workflow_handle(
            workflow_id="sentiment-analyzer"
        )
        
        while True:
            # Execute the scraping activity
            scraped_data = await workflow.execute_activity(
                scrape_reddit,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            )
            
            # Send the scraped data to the sentiment analyzer workflow via signal
            await sentiment_analyzer.signal("new_content", scraped_data)
            
            # Wait for 1 hour before next scrape
            await workflow.sleep(timedelta(seconds=30))

@workflow.defn
class SentimentAnalyzerWorkflow:
    def __init__(self) -> None:
        self._content_queue: list[ScrapedData] = []
        self._processing_signal = False
        self._new_content_available = False
    
    @workflow.signal
    async def new_content(self, scraped_data: ScrapedData) -> None:
        """Signal handler for receiving new content"""
        self._content_queue.append(scraped_data)
        self._new_content_available = True
        workflow.logger.info(
            f"Received {len(scraped_data.items)} items from {scraped_data.platform} "
            f"for analysis"
        )
    
    @workflow.run
    async def run(self) -> None:
        workflow.logger.info("Starting sentiment analyzer workflow")
        
        while True:
            # Wait until new content is available
            def has_content():
                return self._new_content_available
            
            # Only wait if there's no content to process
            if not self._new_content_available:
                await workflow.wait_condition(has_content)
            
            # Process all available content
            while self._content_queue:
                # Reset the flag if we're about to process the last item
                if len(self._content_queue) == 1:
                    self._new_content_available = False
                
                # Get the next batch of content
                scraped_data = self._content_queue.pop(0)
                
                workflow.logger.info(
                    f"Processing {len(scraped_data.items)} items from {scraped_data.platform}"
                )
                
                # Analyze sentiment
                sentiment_results = await workflow.execute_activity(
                    analyze_sentiment,
                    scraped_data,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(minutes=1),
                        maximum_attempts=3,
                    )
                )
                
                # Log the results
                workflow.logger.info(
                    f"Analyzed {len(scraped_data.items)} items from {scraped_data.platform}. "
                    f"Average sentiment: {sentiment_results['average_sentiment']}, "
                    f"Distribution: {sentiment_results['distribution']}"
                )

@workflow.defn
class TwitterScraperWorkflow:
    @workflow.run
    async def run(self) -> None:
        # Get the handle to the sentiment analyzer workflow (no await needed)
        sentiment_analyzer = workflow.get_external_workflow_handle(
            workflow_id="sentiment-analyzer"
        )
        
        while True:
            # Execute the scraping activity
            scraped_data = await workflow.execute_activity(
                scrape_twitter,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            )
            
            # Send the scraped data to the sentiment analyzer workflow via signal
            await sentiment_analyzer.signal("new_content", scraped_data)
            
            # Wait for 2 hours before next scrape - longer interval to avoid rate limits
            await workflow.sleep(timedelta(minutes=1)) 