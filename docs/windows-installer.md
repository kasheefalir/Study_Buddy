# Windows Installer (Preview)

The Windows installer bundles Python and the app's Python dependencies. Students
do not need Python, Git, PowerShell commands, or a virtual environment.
Ollama and model weights are not bundled.

## Student Setup

1. Download `StudyBuddy-Windows-Setup.exe` from the Windows installer build artifact.
2. Run it, then open Study Buddy from the Start menu or desktop shortcut.
3. Use **Get Ollama desktop app** if Ollama is missing. Install and open Ollama.
4. In the classroom's model menu, select an available model or download one.
5. Keep the launcher window open. **Quit Study Buddy** stops this app's server,
   not Ollama.

This preview is unsigned. Windows may warn about an unknown publisher. Do not
disable antivirus or system security. Verify the download's origin; managed
school computers may require IT approval.

The installer currently targets Windows x64, not native Windows ARM.

## Data and Updates

The app installs per user under `%LOCALAPPDATA%\Programs\Study Buddy`.
Materials, conversations, and logs live separately under
`%LOCALAPPDATA%\Study Buddy\data`. Uninstalling leaves this data intact.
Existing source-checkout data is not automatically migrated.
The desktop launcher does not register the terminal `study buddy` shortcut.

The source-checkout launch scripts are unchanged. The desktop launcher uses the
first free port starting at 8000, then a system-assigned port if needed. Browser
preferences are per origin, so a different port may have different preferences.
It prevents duplicate packaged instances for the same data directory on Windows.

## Build and Validation

`.github/workflows/windows-installer.yml` builds on a Windows runner using
PyInstaller and Inno Setup. It runs path/socket tests, exercises frozen imports
and browser assets, and checks silent installation/uninstallation. The downloadable
installer is an Actions artifact, not an automatically published release.

Run **Windows installer** through GitHub Actions, or push a packaging change.
The workflow deliberately does not include student materials, evaluation results,
credentials, Ollama, or model weights in the bundle.

Before calling this release-ready, test on a clean Windows machine without Python:
first launch, Ollama installation/detection, model download, file import, chat,
quiz, closing/reopening, occupied port, second launch, upgrade, and uninstall with
saved data retained. CI smoke tests are not a substitute for that walkthrough.
Code signing and a reproducibly locked dependency set remain release work.
