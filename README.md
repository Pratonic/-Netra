# त्रिNetra Campus Access

A campus access application with separate administrator and kiosk sessions, cloud-managed enrollment, time-based authorization, Amazon Rekognition liveness integration and a conservative offline workflow.

## Workspaces

- **Admin** — username `admin`, password `admin`. Enroll people, manage access status and personal schedules, set campus hours/closures, and review or export activity.
- **Access** — username `AWS`, password `AWS`. Identify a person, check campus authorization, and complete an AWS live-presence check. This role cannot change enrollment or schedules.

The application login is layered inside the existing private Site audience. Passwords are checked on the server, not in browser JavaScript. Sessions use random opaque cookies, HttpOnly/Secure flags, an eight-hour expiry and server-side role/CSRF checks. Default shared passwords are configured as requested; change them before expanding access beyond the private workspace.

## Access flow

1. An administrator verifies identity, obtains consent to AWS storage, and enrolls a front portrait, email address and access rules, with up to five face views for pose coverage.
2. The kiosk warms its models and camera. The initial local recognition check has a two-second budget and shows a candidate name when two usable samples agree.
3. The backend checks current campus hours, active status, expiry, personal rules and closure dates. A local face match alone requests **Request verification**, never Allow.
4. With explicit consent, the official AWS Amplify component streams a short live video to Amazon Rekognition.
5. The server retrieves the AWS liveness result, rejects expired/replayed sessions, compares the returned live reference against the enrolled image, and checks permissions again. Only this trusted path can return **Allow**.

Outside configured hours, a person is denied unless their policy requires an attended review. Suspended, expired and campus-closure cases are denied. Overnight windows use the day on which the window began; closing time is exclusive.

The two-second budget is for the initial local check. Cloud liveness is a separate, longer flow. No universal sub-two-second cloud verification or biometric accuracy claim is made.

## Offline behavior

Connection loss clears enrolled identities from application memory and disables automatic access. A recently authenticated kiosk can show safe guidance after a reload without storing its password or identity dataset locally. On-site security performs the attended campus ID and permission check.

An offline record contains only a random event ID, timestamp and `stepup/offline` status. No name, portrait, template or password. The queue holds at most 100 records and removes expired entries on app activity after 24 hours. When connectivity and authentication return, records synchronize idempotently. Supplied Allow records are rejected; sync never grants retrospective access.

A service worker caches static assets, never API responses. First use requires a connection, and an expired kiosk session requires online sign-in.

## AWS architecture

Private Sites gateway → protected Lambda Function URL → Lambda → encrypted DynamoDB and Amazon Rekognition.

The Worker supplies a private gateway secret and authenticated Site visitor identity. The function rejects missing values. Administrative and kiosk authorization are enforced again in Python. The browser receives only a 15-minute STS role restricted to `rekognition:StartFaceLivenessSession`, never the supplied sandbox credentials.

See [AWS-DEPLOYMENT.md](AWS-DEPLOYMENT.md) for exact resources, scoped permissions, costs and retention. The user explicitly approved that plan in chat.

References:

- [Amazon Rekognition Face Liveness](https://docs.aws.amazon.com/rekognition/latest/dg/face-liveness.html)
- [Official component and custom credential provider](https://ui.docs.amplify.aws/react/connected-components/liveness)
- [DigiYatra architecture case study](https://aws.amazon.com/solutions/case-studies/digi-yatra-foundation/)

## Run locally

Requires Node.js and Python 3.12+:

```powershell
npm install
npm run build
python backend/dev.py
```

Open **http://127.0.0.1:8770** in Chrome or Edge. Both accounts work against the local Python service. Development uses an in-memory database, reset when the server stops. Cloud liveness is deliberately unavailable locally; local development never invents an AWS Allow.

Google Fonts is optional. Face recognition models and the library are bundled. AWS liveness uses its official component and network-delivered model/runtime assets.

## Checks

```powershell
npm test
node --check ui/app.mjs
npm run build
```

The 35 backend tests cover role authorization, session/CSRF protection, rate limiting, schedule and overnight boundaries, closures, expiry, liveness replay, revocation during verification, identity mismatch and offline synchronization. Rekognition is mocked in policy tests; live AWS and target-camera testing remain separate.

## Source map

- `ui/` — login, dashboards, local camera matching, offline queue, service worker and AWS liveness component.
- `backend/service.py` — authenticated APIs, persistence, trusted result validation and static delivery.
- `backend/policy.py` — schedule decisions.
- `backend/iam-plan.json` — exact trust and permissions.
- `backend/provision.py` — approved-resource provisioning/packaging.
- `backend/dev.py` — loopback development service.
- `worker/index.js` — private Site gateway.
- `assets/` — bundled face-api.js library/models and license.
- `tests/` — backend security and policy tests.

## Deployment boundaries

A physical gate needs an authenticated controller and enforcement integration. Rollout also requires camera-injection defenses, calibrated thresholds, adversarial tests on the intended hardware, monitoring and individual accounts. Details are kept in documentation and the expandable System panel so the main workflows remain concise.

## Local update: pose, decisions and email

Recognition now uses SSD MobileNet, full landmark alignment, higher-resolution frames and multiple enrollment views. The compact result panel covers Allow, Deny and Request verification. Email codes use an SES adapter, but sending is disabled until a verified sender and scoped permission are configured. A successful code confirms the mailbox for an attended ID check; it does not unlock the gate.

Read [research and repository decisions](RESEARCH.md), [email activation](EMAIL-SETUP.md), and the [minimal hardware plan](HARDWARE.md). The two-second initial check is a deadline, not a measured device-wide guarantee. Real-camera pose/range/PAD evaluation and real SES delivery are still outstanding.

Run `npm run build`, `npm test`, then `python -X utf8 backend/dev.py` for local review at `http://127.0.0.1:8770`. The local server keeps data only in memory and has no cloud liveness or email sender. `TRINETRA_DEV_PORT` can select another loopback port. No local test automatically pushes or deploys.
