# Aegis AWS deployment — approval scope

Account **010526260400**, region **us-east-1**. The supplied AWS session has been authenticated successfully. The user explicitly approved this plan in chat. The listed IAM roles, table, function, protected URL and log retention have been provisioned.

Automatic approval review rejected (1) creating a new persistent IAM trust relationship and (2) creating billable shared storage for identity data. The user then explicitly approved this access, storage and cost scope. Provisioning proceeded within that approval.

## Approved resources

- **DynamoDB `AegisCampus`**: one on-demand encrypted table, capped at 10 read and 10 write request units. It stores enrolled names, consent flags, reference portraits, face descriptors, schedules, hashed session identifiers and decision history.
- **Lambda `AegisCampusService`**: Python service, 512 MB memory, 25-second timeout, reserved concurrency 2. It authenticates the requested admin/access accounts, enforces role and CSRF checks, evaluates schedules, validates Rekognition results and synchronizes anonymous offline events. It also serves the app assets through the private Site gateway.
- **IAM `AegisCampusService`**: trusted only by Lambda. Permissions are limited to item operations on the one table, writes to this function's log group, three Rekognition verification APIs, and assuming the stream role.
- **IAM `AegisLivenessStream`**: trusted only by the service role. It grants only `rekognition:StartFaceLivenessSession`. The signed-in browser receives credentials for that action for 15 minutes. It cannot read identities, retrieve results, create other resources or manage AWS.
- **CloudWatch `/aws/lambda/AegisCampusService`**: application error codes only; three-day retention. Passwords, AWS tokens, portraits, video and request bodies are not logged.
- **Lambda Function URL**: reachable over the Internet, but every request is rejected without the private gateway secret and a valid Sites visitor identity. The AWS function URL itself is not shared as the user-facing app. The existing Site remains owner-private and proxies authenticated requests.
- **Sites runtime secrets**: the origin URL and generated gateway secret. Temporary sandbox credentials are not placed in source, browser code or production environment variables.

The exact trust and permission documents are in [backend/iam-plan.json](backend/iam-plan.json). Rekognition's listed liveness APIs require `Resource: "*"`; the role does not grant unrelated Rekognition or AWS administration actions.

## Data retention

New enrollment requires the administrator to confirm identity verification and consent to AWS storage. Existing data from the old local-only app is **not automatically migrated**.

Reference portraits, names and descriptors remain until administrator deletion. Decision events expire after seven days; sessions expire after eight hours and are rejected immediately after expiry. DynamoDB TTL cleanup is asynchronous and may physically remove expired rows later. The app excludes expired rows immediately.

Short liveness video is streamed to Amazon Rekognition only after a person explicitly consents and starts the AWS check. The application does not retain that video or returned live reference images. A confidence score and final decision may be retained in the decision event. AWS's service data handling applies to Rekognition requests.

Offline storage holds only an anonymous event ID, timestamp and `step-up/offline` status. Maximum 100 records, purged on app activity after 24 hours and removed on acknowledged sync. It holds no enrolled names, face templates, portraits or passwords. Offline records cannot grant access.

## Cost and exposure

These are billable sandbox resources. Costs depend on requests, Lambda runtime, data storage/transfer and the number of Rekognition checks. The throughput and concurrency limits constrain traffic but do not establish a monetary spending cap. No reserved capacity, domain, paid subscription or unrelated infrastructure will be created.

The two shared account passwords are configured exactly as requested and stored as salted password hashes in the backend configuration. They should be changed before extending the audience. The existing private Site access boundary remains in place.

## Approval record

The user selected “Approve AWS deployment” for these resources, scoped IAM trust/permissions, the protected Function URL, the described data storage and billable usage, and deployment to the existing private Site. The private audience is preserved.
