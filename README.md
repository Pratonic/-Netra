# Aegis — Face Liveness & Identity

A working, local-first hackathon web prototype with two dashboards: administrator enrollment and camera verification. It includes a labeled test lab, real browser face recognition, active liveness prompts, session export and architecture references.

## Run locally

Requires Python 3 for the static server. No package installation, API key or cloud account is required.

From this folder:

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8766` in a current Chrome or Edge browser. Camera access requires localhost or HTTPS. Do not open `index.html` directly with a `file://` URL.

The pre-trained models and library are bundled. Google Fonts is optional; system fonts work when offline. Face video and enrollment data are never sent to a biometric service. Hosted application source does not contain enrolled identities.

## Use the app

1. **People & enrollment:** enroll a consenting person. Enter a full name and optional team/reference ID. Capture a webcam portrait or upload a clear JPEG, PNG or WebP. The app must find exactly one face and extracts a 128-dimensional descriptor. Confirm that an administrator has independently verified identity and consent before saving.
2. **Live verification:** enable the camera and wait for model initialization. Face forward and click Start verification. Follow the randomly selected blink, left-turn or right-turn prompt immediately.
3. The result shows the matched name only when identity is sufficiently certain. **Allow** requires a strong, consistent identity match, a completed active prompt and an active enrollment. **Deny** covers clear identity mismatch, multiple people or suspended enrollment. **Request verification** handles uncertainty, missing usable evidence or timeout.
4. **Test lab:** choose a known ground-truth condition (genuine enrolled person, print, screen, video or mask), then run a camera check. Review measured results and export CSV.
5. Suspend identities to revoke prototype access; delete them to remove their photo, descriptor and named history. The architecture page can erase all local data.

Each browser/origin has its own dataset. The admin and kiosk share data only within that browser profile and origin. This is a supervised local admin workspace; it is not an authenticated multi-device admin service.

## Two-second budget

The timed interval starts when the prompt is displayed, after camera and model loading. A timer finalizes around 1.99 seconds unless sufficient evidence resolves earlier. The policy rejects an allow when recorded elapsed time exceeds 2,000 ms. Asynchronous inference results arriving after finalization are discarded.

JavaScript scheduling, cold shaders, CPU speed, camera quality and user response time affect latency. A browser cannot offer a hard real-time guarantee. The actual elapsed time is recorded; the UI reports overruns, mean, P95 and fraction within the budget. No sub-two-second recognition benchmark has been established on the user's webcam.

## Recognition and liveness

- face-api.js 0.22.2: Tiny Face Detector, tiny 68-point landmarks and face recognition model, distributed with the upstream MIT license. Models come from the upstream repository's weights directory.
- Euclidean descriptor distance: strong match at `<= 0.48`; unknown above `0.64`; intermediate values request verification. A minimum margin of `0.08` between the best and next identity is required. These are prototype defaults, not calibrated probabilities or accuracy claims.
- At least two usable frames must select the same identity. The maximum observed match distance is used for the decision. Face size, brightness and contrast checks reject weak captures.
- A blink uses an open–closed–open eye landmark sequence; turns use change in nose position relative to the eyes. Thresholds are heuristics and need subject/camera calibration.

**Security limitation:** active prompts alone do not prove a real person is present. Videos containing the requested action, masks, manipulated media, virtual cameras and client-side tampering can defeat this app. No trained passive presentation-attack detector, depth/IR sensing, trusted camera attestation or ISO/IEC 30107-3 evaluation is included. A failed prompt produces review, not a claim that a spoof was positively detected. Allow is a prototype result and must not unlock a real access gate.

## DigiYatra research and adaptation

The Ministry of Civil Aviation's policy describes liveness-enabled selfie enrollment and comparison against an e-KYC reference before credential creation. AWS's DigiYatra case study describes credentials stored on the passenger's smartphone, sharing with the airport verifier and matching a live capture with the reference identity.

AAI's FRT specification (§6.7.3) calls for passive liveness and fake detection without requiring head/facial movement. Public sources do not reveal the proprietary anti-spoof model, training procedure or thresholds. This app borrows the separation of enrollment, liveness, matching and decision, but uses an active heuristic and local admin enrollment instead of reproducing DigiYatra's implementation. The challenge sheet's two-second target is independent of DigiYatra's published operating times.

Primary references:

- [MoCA DigiYatra policy](https://civilaviation.gov.in/sites/default/files/2023-07/Digi%20Yatra%20Policy%20%28DIGI%20YATRA%29.pdf)
- [AWS DigiYatra Foundation case study](https://aws.amazon.com/solutions/case-studies/digi-yatra-foundation/)
- [AAI implementation requirements](https://www.aai.aero/sites/default/files/basic_page_files/Request%20for%20Budgetary%20Offer_DigiYatra_ATD.pdf)
- [face-api.js source and documentation](https://github.com/justadudewhohacks/face-api.js)

## Storage and production work

Reference thumbnails, descriptors, consent flags and names are stored in browser localStorage. They are **not encrypted at rest** and are accessible to someone with that browser profile. Session history is capped at 500 rows. Do not use actual identity documents or production personal data in this prototype.

A production AWS design would add authenticated admin enrollment (for example Cognito), an authorized API, protected template storage, fresh short-lived server sessions, evaluated passive PAD, calibrated face matching, auditable policy decisions and explicit retention controls. AWS credentials and sandbox access were not supplied; no AWS infrastructure is configured or claimed.

## Measurements

CSV includes source/demo flag, operator label, decision, reason, measured elapsed milliseconds, distance, prompt and usable frame count. Simulations are labeled and excluded from all measured metrics. Distances are not confidence percentages.

The lab reports attack allows divided by labeled attacks, genuine non-allows divided by genuine attempts (review included), review rate, mean/P95 latency and the within-budget fraction. These operational metrics are not a certified PAD evaluation. A review is not a confirmed attack rejection. Use controlled subjects, genuine enrollments, varied conditions and each of the attack types on the sheet before reporting detection performance.

## Checks

```powershell
node --check dist/app.mjs
node check.mjs
```

The policy checks exercise allow, timeout, multiple faces, low quality, changing identities, mismatch, ambiguous distance/margin, suspension, failed active prompt and missing identity. They also check nearest identity selection, labeled metric denominators, P95 and demo exclusion. Webcam liveness and attack-resistance testing must still be performed on the intended kiosk hardware.

Source: `dist/index.html`, `dist/style.css`, `dist/app.mjs`, `dist/decision.mjs`. Deployment metadata is in `.openai/hosting.json`.
