import httpx


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base = "https://api.github.com"
        self._client: httpx.AsyncClient | None = None

    async def start(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        resp = await self._client.get(
            f"{self.base}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        resp = await self._client.get(
            f"{self.base}/repos/{owner}/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.v3.raw"},
            params={"ref": ref},
        )
        resp.raise_for_status()
        return resp.text

    async def post_review(
        self, owner: str, repo: str, pr_number: int, commit_sha: str,
        comments: list[dict], body: str,
    ) -> dict:
        resp = await self._client.post(
            f"{self.base}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json={
                "commit_id": commit_sha,
                "body": body,
                "event": "COMMENT",
                "comments": comments,
            },
        )
        resp.raise_for_status()
        return resp.json()
