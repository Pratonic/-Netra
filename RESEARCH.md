# त्रिNetra research and implementation notes

These are local changes prepared on 14 November 2026. They have not been deployed. Research motivates design choices; it does not establish the accuracy or speed of this installation.

## What changed and why

| Change | Repository idea / research basis | Implemented boundary |
| --- | --- | --- |
| Better small-face detection | [face-api.js](https://github.com/justadudewhohacks/face-api.js) documents SSD MobileNet as better at small faces than its Tiny detector; [SSD, Liu et al.](https://arxiv.org/abs/1512.02325) describes the detector family | SSD replaces the 320-pixel Tiny pipeline. Webcam requests 1280×720; recognition retains up to 960 pixels. A face must retain at least 80×80 pixels and be fully in frame. Requested camera resolution is not guaranteed by the browser. |
| Face alignment and several reference views | [dlib recognition example](https://github.com/davisking/dlib/blob/master/examples/dnn_face_recognition_ex.cpp); [FaceNet, Schroff et al., CVPR 2015](https://openaccess.thecvf.com/content_cvpr_2015/html/Schroff_FaceNet_A_Unified_2015_CVPR_paper.html) supports embedding-distance recognition | Full 68-point landmarks align the descriptor input. Enrollment accepts 1–5 views; front, gentle left and gentle right are recommended. Existing single-view identities still work. This app uses face-api's dlib-style recognition network, not a newly integrated FaceNet model. |
| Ambiguous matches request verification | Embedding-distance separation and repeated observations are engineering controls informed by metric recognition | Existing distance ≤0.48 and runner-up margin ≥0.08 remain. Two consecutive usable observations must agree. These thresholds require deployment-specific calibration; they are not published accuracy guarantees. |
| Preserve PAD separately from recognition | [Ming et al., 2020 survey](https://www.mdpi.com/2313-433X/6/12/139), and Wang et al. below | A candidate match never automatically grants entry. The existing trusted AWS liveness + live identity comparison + current access rules remain necessary for automatic Allow. |
| Compact result panel | Product requirement | Every outcome shows the same person/details/time/confidence structure. Unknown identities show an explicit placeholder. Confidence is the actual returned AWS liveness score, not a transformed descriptor distance or claimed probability of correct identity. |

Natural roll and moderate turns should be easier to handle. Fully turned-away faces, severe pitch, occlusion, blur and insufficient pixels cannot be made pose-independent by a UI change. Larger images and SSD cost more computation: the two-second initial deadline still returns a request for verification if the device cannot finish confidently. Cloud liveness and email interaction are separate, longer stages.

## Repositories examined

- **face-api.js (MIT code):** implemented its alternative SSD detector, full landmark alignment and multiple-reference descriptor matching through the existing library. Added the corresponding upstream model assets; retained the bundled license and recorded checksums in `assets/MODEL-SOURCES.json`.
- **dlib:** examined its aligned face-chip / metric-recognition example. Used the approach through the existing face-api pipeline; did not copy a separate native runtime.
- **[Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) (Apache-2.0 code):** examined MiniFASNet, expanded face crops and scale-aware preprocessing. Its own documentation warns about camera/scene dependence and face angles. Did not silently substitute its pretrained RGB score for trusted liveness; adoption needs camera-specific PAD evaluation and a compatible inference runtime.
- **[InsightFace](https://github.com/deepinsight/insightface):** considered SCRFD/ArcFace as a future detector/recognizer replacement. Its published pretrained models carry noncommercial research restrictions unless separately licensed. No InsightFace weights were added to this product.

Repository licenses and pretrained-weight/data rights are separate considerations. The existing upstream MIT notice is preserved; this is not a certification of training-data rights or commercial biometric compliance.

## What the silicone-mask paper contributes

[Wang et al., Neurocomputing 458 (2021), 416–427](https://www.sciencedirect.com/science/article/abs/pii/S0925231221009371) combines spatial texture evidence with temporal facial-motion evidence. The abstract supplied in the project describes SMFMVD as 200 real and 200 silicone-mask videos from 20 subjects. Its saliency process models attention computationally; it is not a separate eye-tracking sensor. Saliency-weighted LBP captures local appearance, saliency-guided oriented optical flow captures motion, and an SVM combines the features.

The practical lesson is to assess material appearance and local nonrigid motion together: moving a head alone is weak evidence because a mask can move with it. A useful future experiment would stabilize the face, measure motion around eyes/mouth separately from rigid head motion, and evaluate on subject-disjoint train/test splits. Do not put clips from one participant into both training and testing. Compare RGB-only, IR-only and fusion on previously unseen participants and spoof materials.

This update does **not** claim to reproduce Wang's model, possess SMFMVD, or inherit its reported performance. The publisher full text was inaccessible during this work; interpretation uses the supplied abstract and searchable publisher metadata. Blink, smile or head turn alone must not produce Allow.

## Email fallback

Six digits were chosen instead of four: 1,000,000 possible values versus 10,000. This is a lower-assurance attended recovery workflow. [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html) does not permit email as its out-of-band authentication channel; this product makes no NIST AAL compliance claim for email.

A fresh, session-bound server review creates a single-use challenge. Codes expire after three minutes, are stored only as keyed hashes, allow at most five guesses per challenge, and have person-wide send/attempt limits across sessions. Revocation, email changes, current hours and recent PAD denials are checked again. Successful email confirmation remains Request verification and asks for an attended ID check; it does not bypass a spoof result, closed campus or unknown identity.

See `EMAIL-SETUP.md` for activation prerequisites, and `HARDWARE.md` for the minimal sensor proposal and evaluation plan.
