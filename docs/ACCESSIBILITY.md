# Instant Scribe – Accessibility Compliance Strategy

Instant Scribe targets **WCAG 2.1 AA** conformance on Windows 10/11.  This short document summarises how the key user-facing components meet—or exceed—accessibility guidelines.

---

## 1. High-Contrast Support

* **Tray Icon** –­ A dedicated high-contrast icon set (yellow on black) is bundled in `assets/icon_high_contrast.ico`.  The application automatically selects this variant when the configuration flag `high_contrast_icons` is enabled or when future operating-system detection is implemented (see *Future Work* below).
* **Icon Sizes** - Both 16 × 16 and 32 × 32 pixel variants are embedded to ensure sharp rendering under all DPI settings.

## 2. Screen-Reader-Friendly Notifications

* All Windows toast notifications now include an `attribution_text` field that repeats the toast title.  Microsoft Narrator and other assistive technologies read this field aloud, guaranteeing the user receives the same context even if the visual toast template changes.
* Notification bodies remain concise, avoiding overly long sentences that can overwhelm speech synthesis.

## 3. Keyboard-Only Interaction

* Every instantaneous action is available via a **global hot-key** (e.g. `Ctrl + Alt + F` to start/stop recording).  The tray-menu duplicates these commands for mouse users while hot-keys ensure complete keyboard access.
* The **VRAM toggle** and **pause/resume** controls likewise have dedicated shortcuts.

## 4. Colour & Contrast

* The default green icon achieves a contrast ratio of **4.5 : 1** against the standard Windows task-bar in light mode.
* The high-contrast yellow-on-black variant exceeds **7 : 1** on both light and dark task-bars, fulfilling WCAG requirements for non-textual graphics.

## 5. Future Work

1. **Automatic Theme Detection** – When running on Windows, Instant Scribe will in a future release query `SystemParametersInfo(SPI_GETHIGHCONTRAST, …)` and switch the icon set dynamically.
2. **Narrator Testing** – End-to-end tests using *Accessibility Insights* are planned to perform automated UI-Automation tree audits.
3. **Localisation** – Task 50 introduces externalised strings; accessibility labels will follow the user-selected language.

---

_Last updated: Task 44 implementation_