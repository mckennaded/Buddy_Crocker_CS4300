import os
from github import Github, Auth
from openai import OpenAI

def initialize():
    try:
        # Get API key and strip any whitespace/newlines
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        # Strip whitespace and newlines
        api_key = api_key.strip()
        
        if not api_key.startswith('sk-'):
            raise ValueError("OPENAI_API_KEY appears to be invalid (should start with 'sk-')")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Get GitHub token and repository info from environment variables
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN is not set")

        repo_name = os.getenv('GITHUB_REPOSITORY')
        if not repo_name:
            raise ValueError("GITHUB_REPOSITORY is not set")

        pr_id = os.getenv('GITHUB_PR_ID')
        if not pr_id:
            raise ValueError("GITHUB_PR_ID is not set")

        # Initialize Github instance with new authentication method
        auth = Auth.Token(github_token)
        g = Github(auth=auth)

        return client, g, repo_name, pr_id
    except Exception as e:
        raise ValueError(f"Failed to initialize: {e}")

def get_repo_and_pull_request(g, repo_name, pr_id):
    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(int(pr_id))
        return repo, pr
    except Exception as e:
        raise ValueError(f"Failed to fetch repo or pull request: {e}")

def fetch_files_from_pr(pr):
    try:
        files = pr.get_files()
        diff = ""
        for file in files:
            diff += f"File: {file.filename}\nChanges:\n{file.patch}\n\n"
        return diff
    except Exception as e:
        raise ValueError(f"Failed to fetch files from PR: {e}")

def request_code_review(diff, client):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are an expert code reviewer specializing in Django" 
                    "web applications, Python best practices, and collaborative" 
                    "software development. Your role is to provide constructive," 
                    "actionable feedback that helps improve code quality," 
                    "maintainability, and team collaboration."

                    "When reviewing code, focus on:"
                    "1. Code Quality: Adherence to Python PEP 8 standards," 
                    "   Django best practices, and DRY principles"
                    "2. Security: Identify potential vulnerabilities, SQL injection" 
                    "   risks, XSS issues, and authentication/authorization problems"
                    "3. Performance: Database query optimization (N+1 queries)," 
                    "   caching opportunities, and resource efficiency"
                    "4. Maintainability: Code readability, clear naming conventions," 
                    "   proper documentation, and modular design"
                    "5. Testing: Test coverage gaps, edge cases, and potential" 
                    "   failure scenarios"
                    "6. Django-Specific: Proper use of models, views, templates," 
                    "   forms, middleware, and static file handling"

                    "Provide feedback that is:"
                    "- Specific and actionable with code examples when relevant"
                    "- Constructive and educational, explaining the 'why' behind suggestions"
                    "- Prioritized by severity (critical security issues vs. minor style improvements)"
                    "- Balanced, acknowledging both strengths and areas for improvement"

                    "Format your review with:"
                    "- A numerical score out of 10 with brief justification"
                    "- 3-4 prioritized suggestions maximum (only if necessary)"
                    "- Direct code references when suggesting changes"
                    "- Clear explanations of potential impact"
                    )},
                {"role": "user", "content": (
                    "Review this pull request for a Django recipe management" 
                    "   web application (Buddy Crocker)."

                    "Context:"
                    "- Project: Team-based Django web application with Bootstrap frontend"
                    "- Focus areas: Code quality, Django best practices, security," 
                    "   performance, and maintainability"
                    "- Target: Production deployment on Render with PostgreSQL database"

                    "Code changes:"
                    "{diff}"

                    "Please provide:"
                    "1. Overall quality score (X/10) with brief justification"
                    "2. Up to 3-4 specific, actionable improvements (only if necessary)"
                    "3. Direct code references for each suggestion"
                    "4. Explanation of potential impact for each issue identified"

                    "Keep feedback concise, constructive, and focused on the most important improvements."
                )}
            ],
            max_completion_tokens=2048,
            timeout=60.0
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Full error: {repr(e)}")
        if hasattr(e, '__cause__'):
            print(f"Underlying cause: {e.__cause__}")
        raise ValueError(f"Failed to get code review from OpenAI: {e}")

def find_existing_ai_comment(pr):
    """
    Find an existing AI review comment on the PR.
    Returns the comment object if found, None otherwise.
    """
    try:
        # AI comments will have a unique identifier in the body
        ai_comment_marker = "<!-- AI Code Review -->"
        
        comments = pr.get_issue_comments()
        for comment in comments:
            if ai_comment_marker in comment.body:
                return comment
        
        return None
    except Exception as e:
        print(f"Warning: Failed to search for existing comments: {e}")
        return None

def post_or_update_review_comments(pr, review_comments):
    """
    Post a new AI review comment or update an existing one.
    """
    try:
        # Add marker to identify AI comments
        ai_comment_marker = "<!-- AI Code Review -->"
        formatted_comment = f"{ai_comment_marker}\n\n## 🤖 AI Code Review\n\n{review_comments}"
        
        # Check for existing AI comment
        existing_comment = find_existing_ai_comment(pr)
        
        if existing_comment:
            # Update existing comment
            existing_comment.edit(formatted_comment)
            print(f"Updated existing AI review comment (ID: {existing_comment.id})")
        else:
            # Create new comment
            pr.create_issue_comment(formatted_comment)
            print("Created new AI review comment")
            
    except Exception as e:
        raise ValueError(f"Failed to post or update review comment: {e}")

def main():
    try:

        client, g, repo_name, pr_id = initialize()

        repo, pr = get_repo_and_pull_request(g, repo_name, pr_id)

        diff = fetch_files_from_pr(pr)

        review_comments = request_code_review(diff, client)

        post_or_update_review_comments(pr, review_comments)

        print("Code review posted successfully.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()