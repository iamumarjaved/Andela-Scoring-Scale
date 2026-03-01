"""GitHub REST API client with automatic pagination and rate-limit handling."""

import time
import requests


class GitHubClient:
    """Wrapper around the GitHub REST API v3.

    Provides methods for fetching repositories, commits, pull requests,
    issues, and comments with automatic pagination, retry/backoff on
    server errors, and rate-limit sleep.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token):
        """Initialize with a GitHub personal access token.

        Args:
            token: GitHub PAT with repo read access.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        })

    def _request(self, url, params=None, max_retries=3):
        """Make a GET request with retry, backoff, and automatic pagination.

        Handles rate limiting by sleeping until the reset window, retries
        on 5xx errors with exponential backoff, and follows pagination
        links to collect all results.

        Args:
            url: The full API URL to request.
            params: Optional query parameters dict.
            max_retries: Maximum retry attempts per page.

        Returns:
            A list of results (for paginated endpoints) or a single dict.
        """
        results = []
        backoff = 1

        while url:
            for attempt in range(max_retries):
                resp = self.session.get(url, params=params)

                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait = max(reset - int(time.time()), 1)
                    print(f"Rate limited. Sleeping {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code >= 500:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    results.extend(data)
                else:
                    return data

                break
            else:
                resp.raise_for_status()

            url = resp.links.get("next", {}).get("url")
            params = None

        return results

    def get_forks(self, owner, repo):
        """List all forks of a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            List of fork dicts from the GitHub API.
        """
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/forks",
            params={"per_page": 100, "sort": "oldest"},
        )

    def get_commits(self, owner, repo, since=None, until=None, author=None):
        """Fetch commits, optionally filtered by date range and author.

        Args:
            owner: Repository owner.
            repo: Repository name.
            since: Optional ISO timestamp for start of range.
            until: Optional ISO timestamp for end of range.
            author: Optional GitHub username to filter by.

        Returns:
            List of commit dicts.
        """
        params = {"per_page": 100}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        return self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/commits", params)

    def get_commit_stats(self, owner, repo, sha):
        """Fetch line addition/deletion stats for a single commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            sha: The commit SHA.

        Returns:
            Dict with 'additions' and 'deletions' counts.
        """
        data = self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}")
        stats = data.get("stats", {})
        return {
            "additions": stats.get("additions", 0),
            "deletions": stats.get("deletions", 0),
        }

    def get_pull_requests(self, owner, repo, state="all", author=None):
        """Fetch pull requests, optionally filtered by author client-side.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: PR state filter ('open', 'closed', 'all').
            author: Optional username for client-side filtering.

        Returns:
            List of PR dicts.
        """
        prs = self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls",
            params={"per_page": 100, "state": state},
        )
        if author:
            prs = [pr for pr in prs if pr["user"]["login"].lower() == author.lower()]
        return prs

    def get_pr_detail(self, owner, repo, pr_number):
        """Fetch detailed info for a single PR including additions and deletions.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: The PR number.

        Returns:
            Dict of PR details from the GitHub API.
        """
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        )

    def get_pr_reviews(self, owner, repo, pr_number):
        """Fetch reviews on a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: The PR number.

        Returns:
            List of review dicts.
        """
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        )

    def get_pr_review_comments(self, owner, repo, pr_number):
        """Fetch inline review comments on a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: The PR number.

        Returns:
            List of review comment dicts.
        """
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        )

    def get_all_pr_review_comments(self, owner, repo, since=None):
        """Fetch all review comments across all PRs in a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            since: Optional ISO timestamp to filter by.

        Returns:
            List of review comment dicts.
        """
        params = {"per_page": 100, "sort": "created", "direction": "desc"}
        if since:
            params["since"] = since
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/comments", params
        )

    def get_issues(self, owner, repo, creator=None, state="all"):
        """Fetch issues (excluding pull requests) for a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            creator: Optional username to filter by issue creator.
            state: Issue state filter ('open', 'closed', 'all').

        Returns:
            List of issue dicts (PRs filtered out).
        """
        params = {"per_page": 100, "state": state}
        if creator:
            params["creator"] = creator
        issues = self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/issues", params)
        return [i for i in issues if "pull_request" not in i]

    def get_issue_comments(self, owner, repo, since=None):
        """Fetch all issue comments for a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            since: Optional ISO timestamp to filter by.

        Returns:
            List of comment dicts.
        """
        params = {"per_page": 100}
        if since:
            params["since"] = since
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments", params
        )
