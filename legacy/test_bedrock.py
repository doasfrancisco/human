"""Smoke test: call Claude via Amazon Bedrock using AWS_BEARER_TOKEN_BEDROCK.

Setup:
    pip install boto3 python-dotenv

Run:
    python test_bedrock.py
"""

import os
import boto3
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

model_id = "us.anthropic.claude-sonnet-4-6"

response = client.converse(
    modelId=model_id,
    messages=[
        {
            "role": "user",
            "content": [{"text": "Hello, Claude. Answer in one short sentence."}],
        }
    ],
)

print(response["output"]["message"]["content"][0]["text"])
