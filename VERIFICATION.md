# त्रिNetra verification record

- **35 backend tests passed.** Role authorization, credentials, throttling, cookie flags, expiry, viewer binding, CSRF, schedule boundaries, overnight access, timezone handling, closures, suspension, enrollment expiry, prechecks never allowing, trusted liveness decisions, replay rejection, wrong identity, revocation/schedule changes during verification, named-history deletion and safe offline sync were covered.
- JavaScript syntax checks and the official AWS liveness bundle build passed.
- Browser checks confirmed both requested accounts, administrator schedule saving, access-role navigation, safe connection-loss behavior, anonymous fallback recording, reopening from the offline cache, and queue acknowledgment/removal after reconnection and reauthentication.
- AWS STS authentication succeeded in account 010526260400. After explicit user approval, the two scoped roles, encrypted DynamoDB table, Lambda service, protected Function URL and three-day CloudWatch retention were provisioned.
- **10 deployed AWS API smoke checks passed:** gateway rejection without its secret, both role logins, reading shared state, access-role schedule denial, both logouts and invalidated sessions. No human portraits, templates or live video were uploaded during these smoke checks.

Not yet verified: a real person's Rekognition video session, recognition/liveness accuracy against the listed attacks, target-kiosk timing and physical-gate enforcement.

Policy tests use deterministic AWS mocks for the liveness/matching outcomes. They establish server decision/replay behavior, not biometric accuracy. The initial local recognition budget is two seconds; additional cloud liveness may take longer.

## Camera, result-panel and email update (14 November 2026)

- 60 Python tests passed, including 25 new email/enrollment/SES-adapter tests. Seven Node tests passed for face-pixel quality, multi-view matching, ambiguity, consecutive observations, multiple faces and inference timeout behavior.
- Local browser checks passed for both logins, required email / multi-view enrollment controls, and the simplified access panel. Synthetic layout fixtures displayed Allow, Request verification and Deny with person details, time and real-score placeholders. The fixture screenshot is stored separately in the workspace outputs.
- Real browser execution loaded and warmed the SSD detector, full 68-point landmark network and descriptor model without console errors. Cold initialization took approximately 31 seconds in the preview browser; initialization occurs before the timed identity check. This is not a measurement of recognition or PAD accuracy.
- The bundle build and JavaScript/Python syntax checks passed. The new source/model assets must be deployed together when publication is authorized.
- No real email was sent, no SES identity/permission was configured, and no cloud deployment was performed for this update. Email delivery is disabled until its activation prerequisites are met.
- Still unverified: real-person range/tilt recognition, physical-camera latency distribution, actual AWS live-video behavior, real SES delivery, attack acceptance/genuine rejection rates and hardware integration. Test doubles establish decision policy, not biometric performance. Successful email verification requires an attended ID check and never produces automatic Allow.
