# Verification record

Verified during development:

- JavaScript module syntax checks passed.
- Twelve decision-policy cases passed: valid allow, timeout, multiple people, missing face, weak image quality, identity changes, unknown person, ambiguous distance, ambiguous margin, suspended enrollment, incomplete active prompt and missing enrolled identity.
- Nearest identity ranking, demo exclusion, labeled attack/genuine metric denominators, latency P95 and budget fraction passed.
- Local HTTP service returned 200. Dashboard navigation, enrollment dialog, simulated allow animation and explicit demo labeling were inspected in the browser. Demo checks did not increment measured metrics.
- Real Tiny Face Detector + landmark + recognition inference was run against a public upstream test portrait. It detected one face and produced a 128-value descriptor. The portrait was discarded; no named identity or consent record was created.
- The actual enrollment upload flow reached “Face reference ready.” with a correctly cropped reference. Test-only diagnostic pages and portrait assets were removed from the deliverable.
- Cold WebGL full inference on the test portrait took about 2.08 seconds; a subsequent full inference on a resized portrait at input size 416 took about 173 ms. CPU inference took about 7 seconds. These are individual fixture diagnostics, not end-to-end camera benchmarks. Full model warm-up now precedes timed verification.

Not verified:

- Actual webcam recognition and active liveness completion on the user's intended hardware.
- Performance or error rates against print, phone screen, video replay, mask, virtual camera or deepfake attacks.
- A guaranteed end-to-end decision or recognized name within two seconds.
- Production authentication, authorization, server-side freshness, protected biometric storage or AWS integration.

The app records measured camera sessions, requests further verification when evidence or timing is insufficient, and labels demonstration output separately. Passing software policy tests does not establish biometric or presentation-attack accuracy.
