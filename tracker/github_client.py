import time
import requests


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        })

    def _request(self, url, params=None, max_retries=3):
        """GET with retry/backoff and automatic pagination."""
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

            # Follow pagination
            url = resp.links.get("next", {}).get("url")
            params = None  # params are baked into the next URL

        return results

    def get_forks(self, owner, repo):
        """List all forks of a repo (paginated)."""
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/forks",
            params={"per_page": 100, "sort": "oldest"},
        )

    def get_commits(self, owner, repo, since=None, until=None, author=None):
        """Commits in a date range, optionally filtered by author."""
        params = {"per_page": 100}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        return self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/commits", params)

    def get_commit_stats(self, owner, repo, sha):
        """Lines added/deleted for a single commit."""
        data = self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}")
        stats = data.get("stats", {})
        return {
            "additions": stats.get("additions", 0),
            "deletions": stats.get("deletions", 0),
        }

    def get_pull_requests(self, owner, repo, state="all", author=None):
        """PRs filtered by state, optionally by author (client-side)."""
        prs = self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls",
            params={"per_page": 100, "state": state},
        )
        if author:
            prs = [pr for pr in prs if pr["user"]["login"].lower() == author.lower()]
        return prs

    def get_pr_detail(self, owner, repo, pr_number):
        """Single PR detail — includes additions, deletions, comments count."""
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        )

    def get_pr_reviews(self, owner, repo, pr_number):
        """Reviews on a PR."""
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        )

    def get_pr_review_comments(self, owner, repo, pr_number):
        """Review comments on a PR."""
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        )

    def get_all_pr_review_comments(self, owner, repo, since=None):
        """All review comments across all PRs in a repo."""
        params = {"per_page": 100, "sort": "created", "direction": "desc"}
        if since:
            params["since"] = since
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/comments", params
        )

    def get_issues(self, owner, repo, creator=None, state="all"):
        """Issues by creator (excludes PRs)."""
        params = {"per_page": 100, "state": state}
        if creator:
            params["creator"] = creator
        issues = self._request(f"{self.BASE_URL}/repos/{owner}/{repo}/issues", params)
        return [i for i in issues if "pull_request" not in i]

    def get_issue_comments(self, owner, repo, since=None):
        """All issue comments, optionally since a timestamp."""
        params = {"per_page": 100}
        if since:
            params["since"] = since
        return self._request(
            f"{self.BASE_URL}/repos/{owner}/{repo}/issues/comments", params
        )
