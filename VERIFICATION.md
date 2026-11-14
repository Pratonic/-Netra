# Aegis verification record

- **35 backend tests passed.** Role authorization, credentials, throttling, cookie flags, expiry, viewer binding, CSRF, schedule boundaries, overnight access, timezone handling, closures, suspension, enrollment expiry, prechecks never allowing, trusted liveness decisions, replay rejection, wrong identity, revocation/schedule changes during verification, named-history deletion and safe offline sync were covered.
- JavaScript syntax checks and the official AWS liveness bundle build passed.
- Browser checks confirmed both requested accounts, administrator schedule saving, access-role navigation, safe connection-loss behavior, anonymous fallback recording, reopening from the offline cache, and queue acknowledgment/removal after reconnection and reauthentication.
- AWS STS authentication succeeded in account 010526260400. After explicit user approval, the two scoped roles, encrypted DynamoDB table, Lambda service, protected Function URL and three-day CloudWatch retention were provisioned.
- **10 deployed AWS API smoke checks passed:** gateway rejection without its secret, both role logins, reading shared state, access-role schedule denial, both logouts and invalidated sessions. No human portraits, templates or live video were uploaded during these smoke checks.

Not yet verified: a real person's Rekognition video session, recognition/liveness accuracy against the listed attacks, target-kiosk timing and physical-gate enforcement.

Policy tests use deterministic AWS mocks for the liveness/matching outcomes. They establish server decision/replay behavior, not biometric accuracy. The initial local recognition budget is two seconds; additional cloud liveness may take longer.
