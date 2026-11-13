# Deployment plan: Job Tracker on AWS

This document uses ASD-STE100 Simplified Technical English. Sentences are short. Each instruction is one step.

## 1. Context

Today, Job Tracker runs only on your laptop. It has these parts:

- Postgres, in Docker.
- The API, with `uvicorn --reload`.
- The Vite dev server. It sends `/api` requests to the API.

You want to put the app on AWS. Then you and a small number of other persons can use it each day.

The main goal is to learn how to deploy and operate an app with real AWS services. The goal is not to build the 100,000-user design in `docs/SYSTEM_DESIGN.md`.

This plan follows the "About 1k DAU" row of the growth table in that document (DAU = daily active users). For each part of the app, the plan uses a "managed" AWS service. A managed service is a service that AWS operates for you.

The plan does not include parts that the app does not need at this load:

- Redis
- Read replicas
- Multi-AZ (a copy of the database in a second data center)
- Kubernetes

You can add these parts later.

### 1.1 Recommended services

| Part of the app | AWS service |
|---|---|
| API | ECS on Fargate |
| Database | RDS for Postgres |
| React app | S3 + CloudFront |
| Login | Cognito |
| Definition of all the infrastructure | Terraform |
| Deployment | GitHub Actions, with OIDC |

With OIDC, you do not keep AWS keys in GitHub.

Many teams use this setup to run containers on AWS. With it, you do not manage servers. Each service agrees with one part of `SYSTEM_DESIGN.md`.

## 2. Words in this document

| Word | Meaning |
|---|---|
| Container image | A package that holds the API code and all the things that it needs to run. |
| Task (ECS) | One running copy of the container image. |
| Migration | A script that changes the database tables (Alembic). |
| SPA | Single-page app. The React app is an SPA. |
| JWT / token | A signed text that shows who the user is. Cognito gives it to the browser. |
| JWKS | The public keys of Cognito. The API uses them to make sure that a token is real. |
| Origin | The place where CloudFront gets the content (S3 or the ALB). |
| Subnet (public / private) | A part of the network. A public subnet can connect to the internet. A private subnet cannot. |
| Security group | A firewall. It sets which traffic can go in and out of a resource. |
| IaC | Infrastructure as code. You write the AWS resources in files (Terraform). |
| Rollback | Go back to the last version that worked. |

## 3. Target architecture

```
                       Route 53 (jobs.yourdomain.com)
                                   │
                       CloudFront (HTTPS, ACM cert in us-east-1)
                ┌──────────────────┴──────────────────┐
         all other paths                           /api/*
                │                                     │
     S3 bucket (built React app,          Application Load Balancer (HTTPS, ACM)
     private)                                         │  only accepts CloudFront
                                                      ▼
                                      ECS Fargate service: api (1–2 tasks)
                                      image from ECR, secrets from SSM/Secrets Manager
                                        │              │               │
                              RDS Postgres 16    S3 bucket       OpenRouter (LLM)
                              (private subnet)   (resume PDFs)
Cognito user pool ← browser login. The API examines the token with the JWKS of the pool.
CloudWatch Logs + Alarms → SNS email     AWS Budgets → email
GitHub Actions ──OIDC──> ECR push, migrate (ECS run-task), ECS deploy, S3 sync + CloudFront invalidation
```

### 3.1 How a request moves

1. The user opens `https://jobs.yourdomain.com`. Route 53 sends the request to CloudFront.
2. If the path starts with `/api/`, CloudFront sends the request to the ALB (load balancer).
3. The ALB sends the request to an API task on ECS.
4. The API reads and writes data in RDS. It keeps resume PDFs in S3. It sends AI requests to OpenRouter.
5. For all other paths, CloudFront gets the React files from the S3 bucket.

CloudFront serves the React app and `/api` from the same domain. Thus, the browser continues to use relative `/api` URLs, as it does with the Vite proxy. The frontend does not need CORS settings. It does not need an API URL setting.

## 4. AWS services and their functions

| Need | AWS service | Notes |
|---|---|---|
| Keep container images | **ECR** | Give each image a tag with the git SHA. A rule keeps only the last 20 images. |
| Run the API | **ECS on Fargate** | AWS operates the servers. You do not update them. Start with 1 task: 0.25 vCPU and 0.5 GB of memory. Use 2 tasks later. |
| Database | **RDS PostgreSQL 16**, `db.t4g.micro`, 20 GB gp3 | Use one data center (single-AZ) at first. AWS makes a backup each day. You can restore the database to any time in the last 7 days. The database is in a private subnet only. |
| Frontend files | **S3 + CloudFront** | The bucket is private. Only CloudFront can read it (Origin Access Control). Asset file names contain a hash, so browsers can keep them for a long time. Browsers must not keep `index.html` (no-cache). |
| HTTPS and paths | **ALB + ACM**, **CloudFront** behaviours | `/api/*` goes to the ALB. All other paths go to S3. If S3 gives a 403 or 404 error, CloudFront sends `/index.html`. This lets React show the correct page. |
| DNS | **Route 53** | A hosted zone with an alias record. The record points to CloudFront. |
| Login | **Cognito user pool** + hosted UI | Only invited users. Users cannot sign up. You create each user. The API examines each token with the JWKS of the pool. |
| Secrets | **Secrets Manager** (RDS database password) and **SSM Parameter Store** SecureString (OpenRouter key) | When a task starts, ECS puts the secrets into environment variables. Do not put secrets in git or in images. |
| Resume files | **S3** (private, encrypted, with versions) and presigned URLs | This replaces the PDF data in Postgres (deep dive E). You can do this later, in Phase 6. |
| Logs and alerts | **CloudWatch Logs** (keep logs for 30 days), **CloudWatch Alarms** → **SNS** email | Alarms for: ALB 5xx errors, unhealthy tasks, RDS CPU, RDS free storage. |
| Uptime | **Route 53 health check** or a CloudWatch Synthetics canary on `/api/health` | You get an email when the site is down. |
| Cost limit | **AWS Budgets** | You get an email at 50%, 80% and 100% of your monthly budget. Set this up first. |
| Infrastructure as code | **Terraform** (state in S3, with a lock) | Put all the resources in `infra/`. When you stop for a long time, use `terraform destroy` to remove all of them. |
| Login for CI/CD | **IAM OIDC provider for GitHub** | GitHub Actions uses a role with only the permissions that it needs. There are no long-term access keys. |

### 4.1 Network (VPC)

- The VPC uses 2 availability zones (AZs). Each AZ has one public subnet and one private subnet.
- The ALB is in the public subnets.
- RDS is in the private subnets.
- The Fargate tasks are in the **public subnets, with a public IP**. Their security group accepts traffic only from the ALB.

**Why the tasks are in public subnets:** Tasks in private subnets need a NAT gateway to get to the internet (for example, to OpenRouter). A NAT gateway costs approximately $35 each month. This setup does not need one.

The security groups connect in this sequence:

1. CloudFront can connect to the ALB.
2. The ALB can connect to the ECS tasks.
3. The ECS tasks can connect to RDS.

No other traffic can get in.

## 5. Phases

### Phase 0: Make your AWS account safe (approximately 1 hour, do this first)

1. Turn on MFA for the root user.
2. Stop using the root user after this step.
3. Turn on **IAM Identity Center**.
4. Create an admin user for yourself in IAM Identity Center.
5. On your laptop, run `aws configure sso`.
6. Create an **AWS Budgets** alert, for example $30 each month.
7. Turn on Cost Explorer.
8. Select a region:
   - **eu-central-1** has all the services in this plan. The latency from the UAE is satisfactory.
   - **me-central-1** is nearer to the UAE. Before you select it, make sure that it has all the services in this plan.
9. **Note:** The ACM certificate for CloudFront must be in **us-east-1**. This is true for all regions.
10. Register your domain in Route 53. Or, move the DNS of your domain to Route 53.

### Phase 1: Prepare the app for production (on your laptop only)

**Goal:** A production build of the app runs on your laptop with `docker compose -f docker-compose.prod.yml up`. It does not use the Vite dev server.

1. Create `backend/Dockerfile`:
   - Use a multi-stage build.
   - Install the packages with `uv sync --locked --no-dev`.
   - Run the app as a user that is not root.
   - Use this command: `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'`.
2. In `backend/app/config.py`, add these settings: `environment`, `cognito_region`, `cognito_user_pool_id`, `cognito_app_client_id`, `resume_bucket` and `git_sha`.
3. Get `DATABASE_URL` from the environment. On AWS, ECS makes this value from the RDS secret.
4. In `backend/app/main.py`, change `/api/health`:
   - Run `SELECT 1` on the database.
   - Return `version`. The value is the git SHA.
5. Keep the CORS setting for localhost only. Production does not need CORS, because one domain serves all the parts.
6. Create `docker-compose.prod.yml` (for your laptop only). It has 3 services: api, db, and nginx or caddy to serve `frontend/dist`.
7. Use this file to test the image before you send it to AWS.
8. Frontend: `npm run build` already makes `dist/`. Do not change `vite.config.ts`.

### Phase 2: Add users with Cognito (do this before other persons log in)

This phase repairs the "No users" problem in `docs/SYSTEM_DESIGN.md` (Step 4, issue 1).

**Database:**

1. Add a `users` table with these columns: `id`, `cognito_sub`, `email`, `created_at`.
2. Add a `user_id` column to these tables: `applications`, `profile`, `resume_reviews`, `cover_letters`. Make it a foreign key with an index.
3. Write an Alembic migration. It gives all the current rows to your account.
4. `Profile` will have one row for each user. It will not be one row with `id = 1`.

**Backend:**

1. Create `app/auth.py` with a `current_user` dependency.
2. In `current_user`, examine the Cognito access token:
   - Make sure that the signature agrees with the JWKS. Keep the JWKS in a cache.
   - Make sure that `iss`, `client_id` and `exp` are correct.
3. In `current_user`, find the user in the `users` table. If the user is not there, add the user.
4. In each query in `app/routers/*`, use only the rows of the current user (filter by `user_id`).
5. Add `DELETE /api/me`. It deletes the account and all its data.

**Frontend:**

1. Use the Cognito hosted UI for login (authorization code + PKCE).
2. Use the `oidc-client-ts` library or the `aws-amplify/auth` library for this.
3. Change the `api` client so that it adds the bearer token to each request. The hooks in `src/hooks/useApplications.ts` then use the token automatically.
4. Run `npm run gen:api` after you change the backend.

**Tests:**

1. In `tests/conftest.py`, replace `current_user` with two test users: A and B.
2. Add tests that make sure the data of each user stays separate. User B must get a 404 error for the application, profile and AI results of user A.

**Local development:**

1. Add a setting for development only: `AUTH_DISABLED=true`.
2. When this setting is on, the API uses one fixed dev user. Thus, `task dev` continues to work without the internet.

### Phase 3: Create the infrastructure with Terraform (`infra/`)

Do the steps in this sequence. After each step, run `terraform apply`. Then you see each part when it starts.

1. `bootstrap/`:
   - An S3 bucket for the Terraform state, with S3 locking.
   - The GitHub OIDC provider.
   - The deploy role for GitHub Actions.
2. `network.tf`: the VPC, subnets, route tables, internet gateway and security groups.
3. `database.tf`:
   - The RDS subnet group.
   - The RDS instance with `manage_master_user_password = true`. With this setting, AWS creates and keeps the password.
   - A parameter group with `rds.force_ssl=1`. This setting makes all connections use SSL.
4. `ecr.tf` + `ecs.tf`:
   - The ECR repository.
   - The ECS cluster.
   - The task definition. It gets the secrets from Secrets Manager and SSM. It sends logs to CloudWatch (`awslogs`).
   - The ECS service.
   - The task execution role (ECS uses it to start the task).
   - The task role (the app uses it). It gives access only to the S3 resume bucket.
5. `alb.tf`:
   - The ALB.
   - An HTTPS listener with an ACM certificate.
   - A target group. Its health check is `/api/health`.
   - An idle timeout of 120 seconds.
   - **Note:** The listener accepts only requests that have a secret header. CloudFront adds this header. Thus, users cannot go directly to the ALB.
6. `frontend.tf`:
   - The S3 bucket with OAC.
   - The CloudFront distribution with two behaviours:
     - `/api/*`: no cache. Send all headers to the ALB. Set the **origin response timeout to 60 seconds**. The AI review is still synchronous, so it can take a long time.
     - All other paths: the S3 bucket.
   - The SPA error-page fallback (see section 4).
   - The Route 53 alias record.
7. `auth.tf`:
   - The Cognito user pool. Only an admin can create users.
   - The app client.
   - The hosted UI domain.
   - The callback URLs for production and for localhost.
8. `monitoring.tf`:
   - How long to keep the logs.
   - An SNS topic with an email subscription.
   - CloudWatch alarms.
   - The health check.

While you do these steps, write `docs/DEPLOYMENT_AWS.md`. For each resource, write what it does, its cost, and how it connects to the other resources.

### Phase 4: Automatic deployment (`.github/workflows/deploy.yml`)

The workflow starts when you push to `main`. It starts only after the jobs in `ci.yml` are successful.

1. **Log in to AWS:** Use `aws-actions/configure-aws-credentials` with OIDC (`role-to-assume`). Do not keep keys in GitHub.
2. **Backend:**
   - Build the image.
   - Push it to ECR with the tag `:<sha>`.
   - Make a new task definition that uses this image.
3. **Migrate the database:**
   - Run `aws ecs run-task` with the new task definition.
   - Replace the command with `alembic upgrade head`.
   - Wait until the task stops.
   - If the task fails (exit code is not 0), stop the workflow.
4. **Deploy:**
   - Use `aws-actions/amazon-ecs-deploy-task-definition` with `wait-for-service-stability`.
   - Turn on the ECS **deployment circuit breaker with rollback**. If a deployment fails, ECS goes back to the last version automatically.
5. **Frontend:**
   - Run `npm run build`.
   - Run `aws s3 sync dist/`. Give the asset files long cache headers. Give `index.html` no-cache.
   - Make a CloudFront invalidation for `/index.html`. This removes the old copy from the CloudFront cache.
6. **Smoke test:** Run `curl https://jobs.yourdomain.com/api/health`. The result must show the new SHA.

**Manual rollback:**

1. Find the number of the last task definition that worked.
2. Run `aws ecs update-service --task-definition jobtracker-api:<n>`.
3. Do one rollback as practice, before you need it.

**Rule for migrations:** Each migration must work with the old version of the code and with the new version. First, add new columns or tables ("expand"). Then, in a later deployment, remove the old ones ("contract"). Thus, after a rollback, the old code can still read the database.

**Taskfile:** Add these commands to `Taskfile.yml`:

- `task deploy`
- `task rollback`
- `task logs` (`aws logs tail --follow`)
- `task infra:plan`

### Phase 5: Operate the app

**Backups:**

1. RDS makes automatic backups. You can restore to any time in the last 7 days.
2. Before a risky migration, make a manual snapshot.
3. Do a restore test each month:
   1. Restore the backup to a new instance.
   2. Connect to the new instance.
   3. Count the rows and compare them with production.
   4. Delete the new instance.
4. **Note:** If you did not test a restore, you cannot be sure that the backup works.

**Monitoring:**

- Use CloudWatch alarms. SNS sends them to you as emails.
- Use Container Insights to see the CPU and memory of the tasks.
- Optional: use Sentry (free tier). It shows the full error details.

**Control the cost of the AI:**

1. Use a different OpenRouter key for production. Give it a credit limit.
2. Add a small `ai_usage` table in Postgres. It keeps the number of AI requests for each user, for each day.
3. When a user goes above the daily limit, return a 429 error.

**Security:**

- Block all public access to the S3 buckets.
- Keep RDS private. Make all connections use SSL.
- Give each IAM role only the permissions that it needs.
- Add a CloudFront response-headers policy with HSTS and nosniff.
- Turn on Dependabot for pip, npm and GitHub Actions.
- Optional: add an AWS WAF rate-based rule to CloudFront (approximately $6 each month). It blocks users that send too many requests.

**Runbook:** In `docs/DEPLOYMENT_AWS.md`, write the steps for each of these tasks:

- Deploy.
- Roll back.
- Restore the database.
- Change a secret. **Note:** After you change a secret, deploy the ECS service again. The tasks read secrets only when they start.
- Read the logs.
- Invite a user in Cognito.
- Remove all the resources with Terraform, and create them again.

### Phase 6 (optional): More things to learn

- **Async AI** (deep dive A):
  1. Put AI jobs on an SQS queue.
  2. Use a second ECS service to do the jobs. It uses the same image.
  3. The UI asks `GET /jobs/{id}` again and again until the job is done.
  4. Then the 60-second CloudFront limit is not a problem.
- **Resumes in S3** (deep dive E), if you did not do it in Phase 2.
- **High availability:**
  - Turn on RDS Multi-AZ.
  - Run 2 ECS tasks in different AZs.
  - Do a failover test.
- **Staging environment:** A second copy of the app at `staging.`. Use a Terraform workspace or a second stack. Deploy it from a branch.
- **Autoscaling:** ECS adds or removes tasks when the CPU usage changes (target tracking).

## 6. Files to create or change

**Create:**

- `backend/Dockerfile`
- `backend/.dockerignore`
- `docker-compose.prod.yml`
- `backend/app/auth.py`
- `infra/**` (Terraform)
- `.github/workflows/deploy.yml`
- `docs/DEPLOYMENT_AWS.md`

**Change:**

- `backend/app/config.py`
- `backend/app/main.py` (health check)
- `backend/app/models.py`, and add a new Alembic migration
- `backend/app/routers/*` (use only the rows of the current user)
- `backend/tests/conftest.py`, and add the tests for separate user data
- The frontend `api` client and the app shell (login)
- `Taskfile.yml`
- `README.md`

**Do not change now:**

- The synchronous AI requests. They must finish in less than 60 seconds.
- Single-AZ RDS.

Phase 6 has the upgrades for these two items.

## 7. Approximate monthly cost (eu-central-1, on-demand)

| Item | Approximate USD each month |
|---|---|
| ALB | 18 |
| RDS db.t4g.micro + 20 GB | 15 |
| Fargate, 1 task, 0.25 vCPU / 0.5 GB | 9 |
| Public IPv4 addresses (ALB, task) | 7 |
| CloudWatch, Route 53, S3, CloudFront, ECR, Secrets | 3–5 |
| **Total** | **Approximately $50–55**, plus the AI cost (the OpenRouter limit controls it) |

- New AWS accounts get free-tier credits. These credits pay for the first months.
- When you do not use the app, run `terraform destroy`. Then the cost is almost zero. An RDS snapshot costs only some cents.
- This setup costs approximately 10 times more than one VPS. For this money, AWS does the failover, the backups and the updates for you. You also learn how these work.

## 8. How to make sure that each phase is correct

**Phase 1:**

1. Run `docker compose -f docker-compose.prod.yml up` on your laptop.
2. Make sure that the app works.
3. Make sure that `/api/health` shows the database status and the SHA.
4. Make sure that `uv run pytest` and `npm run build` are still successful.

**Phase 2:**

1. Make sure that the tests for two users are successful.
2. Invite two users in Cognito. Log in as each user.
3. Make sure that each user cannot see the data of the other user.

**Phase 3:**

1. After `terraform apply`, run `terraform plan`. It must show no changes.
2. Make sure that the site opens at `https://jobs.yourdomain.com`.
3. Try to connect to RDS from your laptop with `psql`. The connection must fail. This shows that the database is private.

**Phase 4:**

1. Push a small change.
2. Make sure that the workflow migrates the database and deploys the app.
3. Make sure that `/api/health` shows the new SHA.
4. Deploy an image that does not work, on purpose.
5. Make sure that the circuit breaker goes back to the last version.

**Phase 5:**

1. Restore the database to a new instance (point-in-time restore).
2. Stop the service (set the desired count to 0). Make sure that you get the alarm email.
3. Send more AI requests than the daily limit. Make sure that you get a 429 error.
4. Make sure that the budget alert is set up.
