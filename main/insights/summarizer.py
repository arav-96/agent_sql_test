from openai import AzureOpenAI
import os


api_key = os.environ.get("azure_api_key")
azure_endpoint = os.environ.get("azure_endpoint")


# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key = api_key,
    api_version = "2024-12-01-preview",
    azure_endpoint = azure_endpoint
)


def summarize_insights(payload: dict) -> str:
    prompt = f"""
You are a data analyst assistant.

Rules:
- If findings contain a single descriptive result, state the value clearly.
- If findings contain comparisons, describe differences cautiously.
- Do NOT invent trends, causes, or changes.
- Use neutral, factual language.

Findings:
{payload}
"""

    response = client.chat.completions.create(
        model = "gpt-4.1-mini",
        messages = [{"role": "user", "content": prompt}],
        temperature = 0.2,
        max_tokens = 200
    )

    return response.choices[0].message.content

