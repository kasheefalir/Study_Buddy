# Mac App Bundle Preview

The Mac build creates a disk image containing `Study Buddy.app` and an
Applications shortcut. Drag the app to Applications, then open it. Python and
dependencies are bundled. No terminal setup is required.

Separate Apple Silicon and Intel builds target macOS 15 or newer. The GitHub
workflow is `.github/workflows/macos-bundle.yml`. Build artifacts are downloadable
ZIPs containing the DMG, not source code.

## Existing Installation

The bundle uses the Ollama service already installed on your Mac, including its
sign-in and available models. If Ollama is running and cloud access works, no
separate Python configuration is needed. Otherwise, open/sign in to Ollama and
use Retry model setup. Cloud model registration is not proof of account access.

The bundle saves its own data under:

`~/Library/Application Support/Study Buddy/data`

It does not automatically copy materials or conversations from a development
checkout. Quit the development server first to avoid confusion. If port 8000 is
occupied, the bundle uses another free port; always use the URL it opens.
Browser preferences are per origin and can differ on a different port.
Uninstalling the app does not remove saved data. Logs are in `data/logs/desktop.log`.

## Security and Validation

This preview is ad-hoc signed by the packager, not Developer ID signed or
Apple-notarized. Gatekeeper may block downloaded copies. Do not disable Gatekeeper
or remove quarantine attributes as a blanket workaround. Verify the download's
origin and consult https://support.apple.com/102445; managed devices may require IT.

CI tests data paths and instance locking, freezes the app for each architecture,
checks imports and browser resources from the frozen executable, then creates
and verifies the DMG. These tests do not establish that every student's Mac can
launch a quarantined download. A first-run Finder/Gatekeeper walkthrough, Ollama
sign-in, import/chat/quiz, and upgrade testing remain acceptance checks.
