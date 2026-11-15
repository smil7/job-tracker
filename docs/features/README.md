# Feature documentation

Each document explains **what** a feature does, **why** it was built this way, **how** it works, and **which technology** was chosen and why. Read them in order.

| # | Feature | Summary |
|---|---|---|
| 1 | [Login check on the API](01-login-token-check.md) | The API checks the Cognito token and knows who the caller is. |
| 2 | [Each user sees only their own data](02-data-per-user.md) | Owner column, filtered routes, 404 for other users, delete account, isolation tests. |
| 3 | [Login in the browser](03-frontend-login.md) | Cognito hosted UI with PKCE, token on every request, log out. |

These features are Step 1 of the AWS deployment guide. The plan and the guide are local notes and are not in the repo.
