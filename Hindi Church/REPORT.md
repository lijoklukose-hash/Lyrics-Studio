# Reverse Engineering Report — `base.apk` (HindiChurch)

**Analyzed:** 2026-10-30
**Method:** ZIP extraction, JADX 1.5.6 decompilation (DEX + resources), manifest decode, string sweeps, SQLite/JSON/asset inspection.

---

## 1. App Identity

| Field | Value |
|---|---|
| App name | **HindiChurch** |
| Package | `com.filadelfia.hindichurchsongs` |
| Version | 2.1.0 (versionCode **27**) |
| SDK | minSdk 23 / targetSdk 35 / compileSdk 35 |
| Framework | **Flutter** (embedding v2), single Activity `MainActivity` |
| Type | Google Play **App Bundle split** (`STAMP_TYPE_DISTRIBUTION_APK`, `requiredSplitTypes=base__abi,base__density`) |
| Signing | Re-signed by Google Play App Signing (bundletool, CN=Android/Google Inc), SHA-256 `E4:47:79:38:...:93` |
| Build tooling | AGP 8.7.3, Gradle 8.12, Kotlin 2.1.0 |

> **Important limitation:** This is only the *base* split. There is **no `lib/` directory** —
> `libapp.so` (Dart AOT code) and `libflutter.so` live in the separate ABI split APKs, which are
> not part of this file. All business logic (UI, Firestore queries, ad unit IDs, screens) is in the
> Dart layer and is **not present here**. Everything below is what the base APK exposes.

## 2. Permissions (all of them)

- `INTERNET`, `ACCESS_NETWORK_STATE`, `WAKE_LOCK`, `POST_NOTIFICATIONS`
- `FOREGROUND_SERVICE`
- `com.google.android.gms.permission.AD_ID` + AdServices `AD_ID` / `ATTRIBUTION` / `TOPICS`
- `com.google.android.c2dm.permission.RECEIVE` (FCM)
- `com.google.android.providers.gsf.permission.READ_GSERVICES`
- `BIND_GET_INSTALL_REFERRER_SERVICE`, `CHECK_LICENSE`

Notably **absent**: storage, camera, microphone, location, contacts, SMS. The
`requestLegacyExternalStorage="true"` flag is a leftover, not an granted permission.

## 3. Backend / Service Credentials (embedded, extractable)

| Service | Value |
|---|---|
| Firebase project | `hindichurch-lyrics-0xlyxf` |
| Firebase API key | `AIzaSyBdPCzlOA6qV_6A0uoPui3r_HXNL6TasXM` |
| Firebase App ID | `1:914070476092:android:4c8572835b6f2c70e53a39` |
| FCM sender ID | `914070476092` |
| Storage bucket | `hindichurch-lyrics-0xlyxf.appspot.com` |
| OAuth web client | `914070476092-lrjeu7mv3prvap37ln4tiruv7cq3s7pl.apps.googleusercontent.com` |
| AdMob App ID | `ca-app-pub-2085450633573899~1480756918` |
| Branch live key | `key_live_ktxpfyMzIzebSDXSBNjUPmfoDAmLB3Aj` |
| Branch domains | `hindichurch.app.link`, `hindichurch-alternate.app.link` |
| Custom URL scheme | `hindichurch://` |

These are client-embedded secrets by design; exposure is normal **only if** Firebase Security
Rules / App Check are properly configured server-side (cannot be verified from the APK).

## 4. Firebase Features Wired In

`GeneratedPluginRegistrant` + manifest components show:
- **Auth** (email/Google/Apple sign-in, reCAPTCHA, phone auth infra)
- **Cloud Firestore** (main data store)
- **Cloud Functions** (`https://%s-%s.cloudfunctions.net/%s` template)
- **Cloud Messaging** (push notifications, background isolate service)
- **Performance Monitoring**, **Remote Config**, **App Check** (SafetyNet + Play Integrity + debug providers)
- **Installations / ABT / Sessions / Datatransport**

## 5. Flutter Plugin Stack (25 plugins)

cloud_firestore · cloud_functions · connectivity_plus · device_info_plus · firebase_app_check ·
firebase_auth · firebase_core · firebase_messaging · firebase_performance · flutter_branch_sdk ·
flutter_keyboard_visibility · flutter_native_splash · **google_mobile_ads** · google_sign_in_android ·
package_info_plus · path_provider_android · permission_handler_android · share_plus ·
shared_preferences_android · **sign_in_with_apple** · sqflite · url_launcher_android ·
wakelock_plus · webview_flutter_android

## 6. Dart Package Ecosystem (101 packages, from `NOTICES.Z`)

UI/UX: `auto_size_text`, `badges`, `flutter_animate`, `flutter_spinkit`, `flutter_svg`,
`google_fonts`, `octo_image`, `page_transition`, `provider`, `timeago`, `nested`, `easy_debounce`
Data: `rxdart`, `http`, `json_path`, `intl`, `mime_type`, `universal_io`
Content: **`youtube_player_iframe`**, `webviewx_plus`, `flutter_branch_sdk`
Fonts: **Mukta** (Hindi/Devanagari), MaterialIcons, CupertinoIcons, FontAwesome

## 7. Assets & Offline Data

- `assets/sqlite_db_files/offlinelyrics.db` — offline cache DB, **schema only (0 rows)**:
  table `offlinelist(songTitleEnglish, songTitleHindi, firstStanzaEng/ChorusEng/StanzasEng,
  firstStanzaHin/ChorusHin/StanzasHin, songID PK)` → bilingual **Hindi/English church song lyrics**
- `assets/environment_values/environment.json` — Branch config (live key, domains)
- Lottie animations from **jitter.video**: two splash/hero scenes (607×411) and a
  **"bad network"** error animation (512×512, duplicated file)
- Branding: `hc-final-logo-{dark,light}-bg}.png`, `app_launcher_icon.png`, `asdasD.jpg` (1000×608, sloppy filename)
- YouTube iframe player template (loads `youtube.com/iframe_api`)

## 8. Advertising

- Google Mobile Ads (UMP consent SDK included — GDPR/EEA consent dialogs)
- AdMob app ID in manifest; **actual ad unit IDs live in the missing Dart code**
- Resources contain AdMob consent/offline-ad dialogs; string `s7 = "Test Ad"` suggests test units
  were used during development (unverifiable further without `libapp.so`)

## 9. Notable Findings / Risks

1. **Branch `io.branch.sdk.TestMode = true` is set in the production manifest** — the app runs the
   Branch SDK in *test mode* in the released build. Likely an oversight; test-mode links/log
   behavior differ from live and can leak link data to the wrong dashboard environment.
2. **No native code in this file** — analysis of app logic requires the companion ABI split
   (`base-arm64_v8a.apk` etc.) containing `lib/arm64-v8a/libapp.so`, then a Dart AOT dumper
   (e.g. `blutter`, `reFlutter`, `doldump`) to recover classes/methods.
3. Java/Kotlin side is heavily **R8-obfuscated** (single-letter classes), but nothing custom hides
   there: `MainActivity` is an empty `FlutterActivity`; **zero custom MethodChannels** — every
   channel is stock Flutter or Branch SDK. All bespoke behavior is 100% Dart-side.
4. Firebase/AdMob/Branch keys are exposed (expected for mobile clients) — server-side rules are the
   real security boundary and cannot be assessed statically here.
5. `pairip` license check + Play Integrity + split-required flags: standard Play App Bundle
   protections, nothing malicious.
6. No C2, no obfuscation beyond standard R8, no dynamic code loading, no suspicious permissions —
   the DEX payload is entirely well-known Google/Flutter/AdMob/Branch SDK code.

## 10. Directory Artifacts Produced

- `extracted/` — raw APK contents
- `decompiled/sources/` — JADX Java output (all 3 DEX)
- `decompiled_res/resources/` — decoded manifest + resources (`values/strings.xml` has the keys)
- `decompiled_c3/` — classes3.dex (desugared java.time backport)
- `tools/` — jadx 1.5.6 + analysis scripts + `strings_report.txt` (4,492 lines)
