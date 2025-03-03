from data import Content
def create_sentiment_analysis_prompt(content: Content):
    """Create a prompt for sentiment analysis based on content type."""
    # Format content based on platform
    content_to_analyze = ""
    
    if content.platform == "reddit":
        # Format Reddit content with title, text, and top comments
        content_to_analyze = f"""
Title: {content.title}

Content: {content.text if content.text else 'No content'}

Top Comments:
{chr(10).join([
    f"- [{reply.score} points] {reply.content[:200]}..." 
    for reply in content.replies[:3]
])}
"""
    elif content.platform == "twitter":
        # Format Twitter content with tweet and metrics
        content_to_analyze = f"""
Tweet: {content.text}

Engagement: {content.engagement_metrics.get('like_count', 0)} likes, {content.engagement_metrics.get('retweet_count', 0)} retweets
"""
    
    # Create the full prompt with instructions and examples
    prompt = f"""
Analyze the following {content.platform.title()} content and its engagement. Your task has two independent parts:

PART 1: Write a brief summary (2-3 sentences) of the content and discussion.

PART 2: Determine the overall sentiment, considering both the content and responses/engagement.

For the sentiment analysis, think step by step:
1. Identify positive elements (enthusiasm, agreement, helpfulness, optimism)
2. Identify negative elements (criticism, frustration, disagreement, pessimism)
3. Identify neutral elements (factual statements, questions, balanced views)
4. Consider engagement metrics (high engagement might indicate resonance)
5. Weigh these elements to determine an overall sentiment score between 0 and 1 where:
   - 0 is extremely negative
   - 0.5 is neutral
   - 1 is extremely positive

Content to analyze:
{content_to_analyze}

Here are some examples to guide your analysis:

Example 1 (Negative):
Content: "This framework is terrible. Multiple critical bugs reported. Comments agree it's unusable."
Thinking: Strong negative language ("terrible"), technical issues mentioned, community consensus is negative, no positive aspects noted.
Sentiment score: 0.2 (quite negative)

Example 2 (Positive):
Content: "Just released v2.0! 30% performance boost, new features. Community excited, minor bugs reported."
Thinking: Announces improvements, quantified benefits, positive community response, only minor issues noted.
Sentiment score: 0.8 (quite positive)

Example 3 (Neutral):
Content: "Comparing Framework A vs B: A has better performance, B has cleaner syntax. Comments discuss trade-offs."
Thinking: Balanced comparison, no strong bias, discussion focuses on facts, valid points on both sides.
Sentiment score: 0.5 (neutral)

Provide your response in the following JSON format:
{{
    "summary": "your summary here",
    "sentiment_analysis": {{
        "positive_elements": "list key positive aspects",
        "negative_elements": "list key negative aspects",
        "neutral_elements": "list key neutral aspects",
        "engagement_impact": "how engagement affects sentiment",
        "sentiment_score": 0.X,
        "reasoning": "brief explanation of how you arrived at this score"
    }}
}}
"""
    return prompt
