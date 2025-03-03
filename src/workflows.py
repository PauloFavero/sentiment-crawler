from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, List

with workflow.unsafe.imports_passed_through():
    from activities import say_hello, scrape_reddit, analyze_sentiment

@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=3,
            )
        )

@workflow.defn
class RedditScraperWorkflow:
    @workflow.run
    async def run(self) -> Dict:
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
        
        # Perform sentiment analysis on the posts
        sentiment_results = await workflow.execute_activity(
            analyze_sentiment,
            posts,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=3,
            )
        )
        
        # Aggregate results
        aggregated_data = {
            'total_posts': len(posts),
            'sentiment_distribution': sentiment_results['distribution'],
            'posts_with_sentiment': sentiment_results['analyzed_posts'],
            'average_score': sum(post['score'] for post in posts) / len(posts),
        }
        
        # Schedule the next run in 1 hour using a timer
        await workflow.sleep(timedelta(hours=1))
        
        # Start a new workflow instance
        await workflow.start_child_workflow(
            RedditScraperWorkflow.run,
            id=f"reddit-scraper-{workflow.info().workflow_id}",
            task_queue="reddit-tasks"
        )
        
        return aggregated_data 