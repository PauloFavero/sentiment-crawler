from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, List

with workflow.unsafe.imports_passed_through():
    from activities import scrape_reddit, analyze_sentiment

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
            posts = await workflow.execute_activity(
                scrape_reddit,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            )
            
            # Send the posts to the sentiment analyzer workflow via signal
            await sentiment_analyzer.signal("new_posts", posts)
            
            # Wait for 1 hour before next scrape
            await workflow.sleep(timedelta(hours=1))

@workflow.defn
class SentimentAnalyzerWorkflow:
    def __init__(self) -> None:
        self._posts_queue: List[Dict] = []
    
    @workflow.signal
    async def new_posts(self, posts: List[Dict]) -> None:
        """Signal handler for receiving new posts"""
        self._posts_queue.extend(posts)
        workflow.logger.info(f"Received {len(posts)} new posts for analysis")
    
    @workflow.run
    async def run(self) -> None:
        workflow.logger.info("Starting sentiment analyzer workflow")
        
        while True:
            if self._posts_queue:
                # Get the next batch of posts
                posts_to_analyze = self._posts_queue[:]
                self._posts_queue.clear()
                
                workflow.logger.info(f"Processing {len(posts_to_analyze)} posts")
                
                # Analyze sentiment
                sentiment_results = await workflow.execute_activity(
                    analyze_sentiment,
                    posts_to_analyze,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(minutes=1),
                        maximum_attempts=3,
                    )
                )
                
                # Log the results
                workflow.logger.info(
                    f"Analyzed {len(posts_to_analyze)} posts. "
                    f"Average sentiment: {sentiment_results['average_sentiment']}"
                )
            
            # Wait a bit before checking for more posts
            await workflow.sleep(timedelta(seconds=30)) 