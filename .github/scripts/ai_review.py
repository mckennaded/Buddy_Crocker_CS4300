# File: .github/scripts/ai_review.py

import os
import sys
import openai
import requests

# Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
PR_NUMBER = os.environ.get('PR_NUMBER')
REPO = os.environ.get('REPO')

if not OPENAI_API_KEY:
    print("OPENAI_API_KEY not set, skipping AI review")
    sys.exit(0)  # Exit gracefully, don't fail the workflow

openai.api_key = OPENAI_API_KEY

def get_pr_diff():
    """Read the PR diff from file"""
    # Diff is in root directory now
    diff_path = os.path.join(os.path.dirname(__file__), '..', '..', 'pr_diff.txt')
    try:
        with open(diff_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print("No diff file found")
        return ""

def review_code_with_openai(diff):
    """Send code diff to OpenAI for review"""
    
    if not diff or len(diff.strip()) < 10:
        return None  # Skip if no meaningful changes
    
    # Limit diff size
    max_chars = 12000
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n...[diff truncated]"
    
    prompt = f"""You are an expert code reviewer for Buddy Crocker, a Django recipe app.

Review the following Python code changes for:

1. **Security Issues**: Django security (CSRF, SQL injection, XSS, authentication)
2. **Bugs**: Logic errors, type issues, null checks
3. **Best Practices**: Django patterns, PEP 8, code organization
4. **Performance**: N+1 queries, inefficient operations
5. **Testing**: Missing test coverage for new code

Focus on significant issues. Be concise and actionable.

CODE CHANGES:
{diff}

Provide your review in markdown format with specific line references when possible."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert Django code reviewer focused on security and best practices."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        return None

def find_existing_ai_comment():
    """Check for an existing AI Code Review comment on the PR"""
    url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch comments: {response.status_code}")
        return None

    comments = response.json()
    for comment in comments:
        if "AI CODE REVIEW" in comment.get("body", ""):
            return comment["id"]
    return None

def post_review_comment(review_text):
    """Post the AI review as a comment on the PR"""
    url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    comment_body = f"""##AI Code Review

{review_text}

---
*Automated review by GPT-4o-mini • Verify all suggestions • Focus on critical issues*
"""
    
    existing_comment_id = find_existing_ai_comment()
    if existing_comment_id:
        print(f"Updating existing AI review comment (ID: {existing_comment_id})")
        response = requests.patch(
            f"https://api.github.com/repos/{REPO}/issues/comments/{existing_comment_id}",
            headers=headers,
            json={"body": comment_body}
        )
    else:
        print("Posting new AI review comment")
        response = requests.post(base_url, headers=headers, json={"body": comment_body})

    if response.status_code in (200, 201):
        print("✓ AI review comment posted/updated successfully.")
    else:
        print(f"✗ Failed to post/update review: {response.status_code}")
        print(response.text)

def main():
    print("\n========================================")
    print("AI CODE REVIEW")
    print("========================================\n")
    
    # Get the PR diff
    diff = get_pr_diff()
    
    if not diff or len(diff.strip()) < 10:
        print("ℹNo significant Python code changes detected")
        return
    
    print(f"Reviewing {len(diff)} characters of code changes...")
    
    # Get AI review
    review = review_code_with_openai(diff)
    
    if not review:
        print("Could not generate review")
        return
    
    # Post review as comment
    if post_or_update_review(review):
        print("\n✓ AI code review complete!")
    else:
        print("\nReview generated but not posted")
    
    print("========================================\n")

if __name__ == "__main__":
    main()
