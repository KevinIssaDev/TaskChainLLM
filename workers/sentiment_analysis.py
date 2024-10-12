from textblob import TextBlob

def sentiment_analysis(text: str) -> dict:
    """
    Analyzes the sentiment of the given text using TextBlob.

    Args:
        text (str): The text to analyze.

    Returns:
        dict: A dictionary containing the polarity score and sentiment label.

    Example Usage:
        [[WORKER: {"name": "sentiment_analysis", "args": {"text": "This movie was fantastic!"}}]]
    """
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity

    if polarity > 0:
        sentiment = "positive"
    elif polarity < 0:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "polarity": polarity,
        "sentiment": sentiment
    }

worker = sentiment_analysis
