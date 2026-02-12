import json
import os

from openai import AzureOpenAI
from openai import BadRequestError

from prompts.planner_prompt_claims import build_planner_prompt_claims


api_key = os.environ.get("azure_api_key")
azure_endpoint = os.environ.get("azure_endpoint")


client = AzureOpenAI(
    api_key=api_key,
    api_version="2024-12-01-preview",
    azure_endpoint=azure_endpoint,
)


def run_planner_claims(user_question: str) -> dict:
    messages = build_planner_prompt_claims(user_question)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.0,
            max_tokens=300,
        )

        content = response.choices[0].message.content
        return json.loads(content)

    except BadRequestError as e:
        return {
            "error": "CONTENT_FILTERED",
            "error_type": "AZURE_POLICY",
            "message": str(e),
            "question": user_question,
        }

    except json.JSONDecodeError:
        return {
            "error": "INVALID_JSON",
            "error_type": "PARSER",
            "raw_output": content,
            "question": user_question,
        }
