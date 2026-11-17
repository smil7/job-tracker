# Feature documentation

Each document explains **what** a feature does, **why** it was built this way, **how** it works, and **which technology** was chosen and why. Read them in order.

| # | Feature | Summary |
|---|---|---|
| 1 | [Login check on the API](01-login-token-check.md) | The API checks the Cognito token and knows who the caller is. |
| 2 | [Each user sees only their own data](02-data-per-user.md) | Owner column, filtered routes, 404 for other users, delete account, isolation tests. |
| 3 | [Login in the browser](03-frontend-login.md) | Cognito hosted UI with PKCE, token on every request, log out. |
| 4 | [Logs and health check](04-logging-and-health.md) | JSON logs with a request id, AI call logs, a health check that tests the database. |
| 5 | [Daily AI limit](05-ai-daily-limit.md) | Each user can start a limited number of AI requests per day. More gives 429. |
| 6 | [Container image](06-container-image.md) | Dockerfile for the API, and a compose file to test the production build on a laptop. |

Features 1 to 3 are Step 1 and features 4, 5 and 6 are Steps 2, 3 and 4 of the AWS deployment guide. The plan and the guide are local notes and are not in the repo.
