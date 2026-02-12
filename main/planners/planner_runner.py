import json
from openai import AzureOpenAI
from openai import BadRequestError
import os

from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA
from prompts.planner_prompt import build_planner_prompt

from planners.planner_validator import validate_plan
from utils.logger import get_logger

api_key = os.environ.get("azure_api_key")
azure_endpoint = os.environ.get("azure_endpoint")


# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key = api_key,
    api_version = "2024-12-01-preview",
    azure_endpoint = azure_endpoint
)


def run_planner(user_question: str) -> dict:
    messages = build_planner_prompt(
        schema = TAXI_SEMANTIC_SCHEMA,
        user_question = user_question
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.0,
            max_tokens=300
        )

        content = response.choices[0].message.content

        # Enforce JSON parsing
        return json.loads(content)

    except BadRequestError as e:
        # Azure content filter / Responsible AI policy
        return {
            "error": "CONTENT_FILTERED",
            "error_type": "AZURE_POLICY",
            "message": str(e),
            "question": user_question
        }

    except json.JSONDecodeError:
        return {
            "error": "INVALID_JSON",
            "error_type": "PARSER",
            "raw_output": content,
            "question": user_question
        }


if __name__ == "__main__":
    question = "Why did average fare increase by vendor last month?"

    plan = run_planner(question)

    print("PLANNER OUTPUT:")
    print(json.dumps(plan, indent = 2))