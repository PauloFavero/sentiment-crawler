from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import say_hello, scrape_reddit

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
    async def run(self) -> list:
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
        
        # Schedule the next run in 1 hour using a timer
        await workflow.sleep(timedelta(hours=1))
        
        # Start a new workflow instance
        await workflow.start_child_workflow(
            RedditScraperWorkflow.run,
            id=f"reddit-scraper-{workflow.info().workflow_id}",
            task_queue="reddit-tasks"
        )
        
        return posts 