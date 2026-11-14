# Email verification activation

The local code now requires email for new enrollment and permits adding/updating email in an existing person's Access rules. The kiosk receives a masked address; the full address stays in administrator/server data. Existing enrollments without email keep working through liveness or an attendant until an administrator adds their address.

The backend has a boto3 SES sender adapter. Without `SES_FROM_ADDRESS`, `/api/state` reports `emailEnabled:false`; the interface clearly marks email delivery as disconnected. Development and unit tests do not contact AWS or send messages. Tests use an in-memory outbox. No email verification codes are returned by the API or logged.

## When deployment is explicitly authorized

1. Verify a sender identity in SES in the intended Region. Set `SES_FROM_ADDRESS` to that verified address; optional `SES_REGION` defaults to `us-east-1`. Store these as runtime configuration, not browser code. No SMTP password is required: Lambda uses its role.
2. Add `ses:SendEmail` to the existing Lambda role, scoped to the selected SES identity ARN, with a From-address condition for that sender. The current provisioning plan deliberately has not been expanded or applied. Resource ARN shape: `arn:aws:ses:us-east-1:010526260400:identity/YOUR_VERIFIED_IDENTITY`. Replace the placeholder with the actual verified identity before using it.
3. If the account is in the SES sandbox, recipient identities must also be verified. [AWS documents the sandbox restrictions](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html). Sending to arbitrary enrolled emails requires SES production access; sandbox and sender verification are regional. Existing generic AWS sandbox credentials do not establish SES sender/recipient readiness.
4. Deploy the updated Python backend, public model assets and UI together after authorization. Publishing only the new UI against the previous backend/models would leave new enrollment and email APIs incompatible.
5. With the recipient's consent, perform one real delivery test, verify expiry/replay behavior and check bounce/suppression handling. No real delivery or cloud configuration was performed for these local edits.

## Recovery behavior

The user first sees a recognized candidate and permitted campus rules. They choose Send email code, then confirm sending in the dialog. The server sends to the stored address, never to an address supplied by the kiosk request. Entering the correct code marks email confirmed and records an attended verification request. An attendant must still check campus ID and current permissions. Email cannot turn a denied biometric or schedule result into automatic Allow.

A challenge is valid for three minutes, bound to one authenticated session, and consumed once. Five wrong guesses exhaust it; there are also ten verification attempts per person per hour and three sends per person per fifteen-minute window. New scans do not reset the person-wide limits. Codes have purpose-separated HMACs using the existing server gateway secret; rotating that secret invalidates outstanding challenges.

This feature introduces email contact data stored with enrollment until identity deletion. Temporary OTP/review state uses TTLs and explicit expiry checks; DynamoDB's physical TTL cleanup may occur later. No raw code or email is copied into access-decision logs. Changing an enrolled email requires administrator authorization and invalidates outstanding codes for the old address.
