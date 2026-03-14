from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:28080/v1",
    api_key=""
)

response = client.chat.completions.create(
    model="deepseek-r1",
    messages=[
        {"role": "user", "content": "如何用 Python 计算 1+1？"}
    ]
)

print(response.choices[0].message.content)