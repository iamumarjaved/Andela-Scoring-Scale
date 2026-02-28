def discover_learners(github_client, repos_config, excluded_users=None,
                      manual_users=None, bootcamp_start_date=None):
    """
    For each base repo, fetch forks, filter by date and exclusions, merge manual list.

    Args:
        github_client: GitHubClient instance
        repos_config: list of "owner/repo" strings
        excluded_users: set of usernames to exclude
        manual_users: list of dicts [{"username": ..., "fork_repo": ..., "base_repo": ...}]
        bootcamp_start_date: only include forks created on/after this date (YYYY-MM-DD)

    Returns:
        list of dicts: [{"username", "fork_repo", "base_repo"}]
    """
    excluded = {u.lower() for u in (excluded_users or [])}
    seen = set()
    learners = []

    for repo_full in repos_config:
        owner, repo = repo_full.split("/")
        forks = github_client.get_forks(owner, repo)

        for fork in forks:
            # Filter by bootcamp start date
            if bootcamp_start_date and fork["created_at"][:10] < bootcamp_start_date:
                continue

            username = fork["owner"]["login"]
            if username.lower() in excluded:
                continue
            if username.lower() in seen:
                continue
            seen.add(username.lower())
            learners.append({
                "username": username,
                "fork_repo": fork["full_name"],
                "base_repo": repo_full,
            })

    for entry in (manual_users or []):
        if entry["username"].lower() not in seen and entry["username"].lower() not in excluded:
            seen.add(entry["username"].lower())
            learners.append(entry)

    return learners
