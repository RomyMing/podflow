# Third-Party Notices

This document separates source present in the PodFlow repository from software, models, services, fonts, and media obtained at build time or runtime.

## Repository contents

PodFlow's original application code, documentation, product design, and project screenshots are covered by the repository [LICENSE](LICENSE). Package lockfiles and dependency declarations identify required third-party packages, but do not relicense those packages.

The repository does not bundle model weights, provider datasets, paid API content, user audio, generated voice profiles, or production credentials.

## Installed dependencies

Python, JavaScript, operating-system, Docker image, FFmpeg, and transitive dependencies are downloaded from their respective distributors when the project is installed or built. Their own license notices and source repositories are authoritative. Relevant dependency manifests include:

- [`pyproject.toml`](podcast_translator/pyproject.toml)
- [`package.json`](podcast_translator/frontend/package.json)
- [`package-lock.json`](podcast_translator/frontend/package-lock.json)
- Dockerfiles under [`podcast_translator/deploy/dockerfiles`](podcast_translator/deploy/dockerfiles)

## Models and external services

Real mode may download, install, or call the following external components:

| Component | Role | Distribution boundary |
| --- | --- | --- |
| Demucs | source separation | Installed at runtime; no weights are stored in this repository. |
| pyannote.audio and gated Hugging Face models | speaker diarization | Requires the user's Hugging Face account and acceptance of the applicable model terms. |
| faster-whisper / CTranslate2 | speech recognition | Installed at runtime; model artifacts are downloaded separately. |
| VoxCPM | local voice synthesis | Optional external model/runtime; use is governed by its upstream terms. |
| ElevenLabs | hosted voice synthesis | Optional external API governed by the provider's terms and usage policies. |
| DashScope / CosyVoice | hosted voice synthesis | Optional external API governed by Alibaba Cloud's terms and model policies. |
| DeepSeek | text translation | External API governed by the provider's terms and usage policies. |

Users are responsible for checking the current license, geographic availability, commercial-use rules, model access conditions, fees, and acceptable-use policies before enabling any external component.

## Audio, voices, screenshots, and fonts

The product screenshots and design image included in this repository document PodFlow's interface. No third-party podcast episode, speaker recording, cloned voice, or generated output is included as sample media.

Only process audio that you are legally entitled to use. Voice cloning requires the speaker's explicit authorization. Impersonation, fraud, deception, unauthorized biometric processing, and infringement of copyright or personality rights are prohibited.

Browser and system fonts are resolved by the user's runtime environment unless otherwise declared by the frontend dependencies. Any externally obtained asset remains governed by its source terms.
