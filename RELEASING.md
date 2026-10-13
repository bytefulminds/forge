# Releasing Forge

A release is a Git tag `vX.Y.Z`. Pushing the tag starts a pipeline that builds Forge for
macOS, Linux and Windows, smoke tests each build, uploads the files to the project's
package registry and publishes a GitLab release with the notes from `CHANGELOG.md`.

## Checklist

1. **Version.** Set the same version in `pyproject.toml` (`version = "X.Y.Z"`) and
   `src/forge/__init__.py` (`__version__ = "X.Y.Z"`), then run `uv lock` so `uv.lock`
   records it. `tests/test_release.py` fails when the two differ.
2. **Changelog.** Add a section `## [X.Y.Z] - YYYY-MM-DD` at the top of `CHANGELOG.md`.
   It becomes the release notes. Check them with
   `uv run python scripts/release_notes.py vX.Y.Z`.
3. **README.** Update the version line at the top of `README.md`.
4. **Test.** The pipeline on `main` must pass. Also start the manual `test:macos` and
   `test:windows` jobs on our own runners. To try the packages before tagging, run the
   build scripts locally (see below); the `build:*` jobs only run on a tag.
5. **Commit and tag.**

   ```sh
   git commit -am "Release X.Y.Z"
   git tag -a vX.Y.Z -m "Forge X.Y.Z"
   git push origin main vX.Y.Z
   ```

6. **Watch the pipeline.** A tag pipeline only builds and releases (the tests already
   ran on `main`): `build:linux-appimage`, `build:macos` and `build:windows` run by
   themselves (the macOS and Windows runners must be online). The
   `release` job publishes the release once all three succeeded.

If a build fails after the tag is pushed, fix it on `main`, delete the tag
(`git push origin :refs/tags/vX.Y.Z` and `git tag -d vX.Y.Z`), and tag again. Packages
already uploaded for that version can be deleted under *Deploy > Package registry*.

## What the pipeline does

| Job | Runner | Script | Output |
|---|---|---|---|
| `build:macos` | our Mac (tag `macos`) | `packaging/macos/build_dmg.sh` | `Forge-X.Y.Z-macos-arm64.dmg` |
| `build:linux-appimage` | GitLab shared, Debian 12 | `packaging/build_appimage.sh` | `Forge-X.Y.Z-linux-x86_64.AppImage` |
| `build:windows` | our Windows PC (tag `windows`) | `packaging/windows/build.ps1` | `Forge-X.Y.Z-setup.exe` |
| `release` | GitLab shared | `release:` keyword | the GitLab release with links |

The Linux job also checks that the tag matches the version (`scripts/release_notes.py`)
before it builds, so a wrong tag stops the release early.

Files go to the generic package registry at
`/projects/<id>/packages/generic/forge/X.Y.Z/<file>`; the release links point there.

## Building locally

All three scripts freeze Forge with PyInstaller (`packaging/forge.spec`), including the
Qt WebEngine for the full Markdown preview, and then run `forge --smoke-test` on the
result: it starts Forge without a window, checks the bundled files, imports every tool,
opens a few documents and draws a Mermaid diagram. A failing check stops the build.

**macOS** (Apple Silicon, Xcode command line tools):

```sh
bash packaging/macos/build_dmg.sh       # dist/Forge.app and dist/Forge-X.Y.Z-macos-arm64.dmg
```

**Linux** (x86-64; libraries come from the build machine, so build on an old distribution,
CI uses Debian 12):

```sh
sudo apt install binutils curl file libxcb-cursor0
./packaging/build_appimage.sh           # dist/Forge-X.Y.Z-linux-x86_64.AppImage
```

**Windows** (Inno Setup 6 installed):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# packaging\windows\Output\Forge-X.Y.Z-setup.exe
```

The smoke test also works on a source checkout: `uv run forge --smoke-test`.

## Signing

The builds are not signed with an Apple Developer ID or a Windows code signing
certificate yet. The macOS app has an ad hoc signature (Apple Silicon requires one), so
macOS asks once before the first start, and Windows SmartScreen may warn about an unknown
publisher. The release notes and the manual explain both. Signing and notarization can be
added to the build scripts later without changing the rest of the pipeline.

## Pinned tools

- PyInstaller is a pinned dev dependency in `pyproject.toml`.
- `appimagetool` and the AppImage runtime are pinned by version and SHA-256 in
  `packaging/build_appimage.sh`.
- The Windows installer AppId in `packaging/windows/forge.iss` must never change: it ties
  updates and the uninstaller to earlier installs.
