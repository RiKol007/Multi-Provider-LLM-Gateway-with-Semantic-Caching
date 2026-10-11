from locust import HttpUser, task, between
import random

SAMPLE_QUESTIONS = [
    "What's the capital of France?",
    "Explain photosynthesis in one sentence.",
    "What's 15 times 7?",
    "Name three primary colors.",
    "What year did World War 2 end?",
    "Define gravity in simple terms.",
    "What's the boiling point of water?",
    "Who wrote Romeo and Juliet?",
]


class GatewayUser(HttpUser):
    wait_time = between(1, 3)  # simulated users wait 1-3 seconds between requests, like real users would

    @task
    def chat_completion(self):
        question = random.choice(SAMPLE_QUESTIONS)
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": question}],
            },
            headers={"X-User": "testuser"},
        )