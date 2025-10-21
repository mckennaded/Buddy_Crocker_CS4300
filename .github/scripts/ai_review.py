import os
import sys
from openai import OpenAI
import requests

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def get_pr_diff():
    """Read the PR diff from file"""
    try:
        with open('../pr_diff.txt', 'r') as f:
            return f.read()
    except FileNotFoundError:
        print("No diff file found")
        return None

def generate_review(diff_content):
    """Generate AI code review"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # or "gpt-4" if you have access
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert code reviewer. Analyze the code changes and provide constructive feedback on code quality, potential bugs, and best practices."
                },
                {
                    "role": "user",
                    "content": f"Review these code changes:\n\n{diff_content}"
                }
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return None

def post_review_comment(review):
    """Post the review as a PR comment"""
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("REPO")
    pr_number = os.getenv("PR_NUMBER")
    
    if not all([github_token, repo, pr_number]):
        print("Missing GitHub credentials")
        return
    
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    comment_body = f"## 🤖 AI Code Review\n\n{review}"
    
    response = requests.post(url, json={"body": comment_body}, headers=headers)
    
    if response.status_code == 201:
        print("Review posted successfully!")
    else:
        print(f"Failed to post review: {response.status_code}")

if __name__ == "__main__":
    print("=" * 40)
    print("AI CODE REVIEW")
    print("=" * 40)
    
    diff = get_pr_diff()
    
    if not diff:
        print("No changes to review")
        sys.exit(0)
    
    print(f"Reviewing {len(diff)} characters of code changes...")
    
    review = generate_review(diff)
    
    if review:
        print("\nGenerated Review:")
        print(review)
        post_review_comment(review)
    else:
        print("Could not generate review")
        sys.exit(1)
