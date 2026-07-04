"""
options_catalog.py

A data-driven catalog of commonly used Linux/Steam gaming launch options,
grouped into categories. Each Option becomes a checkbox in the Game Editor
UI. Checking the box includes its value in the profile's env_vars /
prefix / suffix string.

target values map directly onto the three fields gamecmd's games.yaml
supports:
    "env"    -> env_vars   (must look like KEY=VALUE)
    "prefix" -> prefix     (a command / wrapper, executed before the game)
    "suffix" -> suffix     (an argument passed after the game binary)

Most options are plain flags/text (`input=()`): the box's `default` is
either a fixed literal (a flag with nothing to configure) or a freeform
string the user can edit directly.

Some options need a *real* value rather than freeform text -- a frame
rate, a resolution, a fixed set of named modes -- so those set `input`
to a tuple of NumberField/ChoiceField descriptors and `default` becomes
a str.format() template referencing each field by name, e.g.:

    OptionDef(..., default="DXVK_FRAME_RATE={fps}",
              input=(NumberField("fps", "FPS", 30, 240, 5, 60),))

The Game Editor renders a Gtk.SpinButton (NumberField) or dropdown
(ChoiceField) per entry in `input`, and resolves the final value via
default.format(**{field_values}).

`group` marks an option as belonging to a compound prefix block that
must be assembled specially rather than just concatenated in order --
currently only "gamescope_block" (see the gamescope category below):
gamescope's own flags have to sit between the literal "gamescope" token
and a closing "--", never just loose in the prefix chain.

`requires` names another option's id that must be checked for this one
to take effect (e.g. a DLSS render-preset override only does anything
if its corresponding *_OVERRIDE=on flag is also set). The Game Editor
disables (and force-unchecks) a dependent option whenever its
requirement isn't met, so a stale/inert value can never silently end
up in the built command.

NOTE ON ACCURACY: values here reflect widely-documented, real flags/env
vars for Proton/DXVK/Wine/gamescope/MangoHud and common engines. A few
(marked with `warning=`) are new, driver-version-dependent, or need
verification per-game -- the UI surfaces those warnings rather than
hiding the uncertainty.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NumberField:
    name: str      # template placeholder key, e.g. "fps"
    label: str     # UI label, e.g. "FPS"
    min: int
    max: int
    step: int = 1
    default: int = 0


@dataclass(frozen=True)
class ChoiceField:
    name: str            # template placeholder key
    choices: tuple        # tuple of (value, display_label) pairs
    default: str


@dataclass(frozen=True)
class OptionDef:
    id: str
    label: str
    target: str  # "env" | "prefix" | "suffix"
    default: str  # literal value, or a str.format() template if `input` is set
    description: str
    warning: str = ""
    input: tuple = ()   # tuple[NumberField, ...] or (ChoiceField,) -- () means plain text/flag
    group: str = ""      # "" = standalone; "gamescope_block" = part of the gamescope ... -- span
    requires: str = ""    # id of another option that must be checked for this one to apply


@dataclass(frozen=True)
class CategoryDef:
    id: str
    title: str
    subtitle: str
    options: tuple  # tuple[OptionDef, ...]


GAMESCOPE_MASTER_ID = "gamescope_enable"
GAMESCOPE_BLOCK_GROUP = "gamescope_block"
GAMESCOPE_CATEGORY_ID = "gamescope"


CATALOG: list[CategoryDef] = [

    CategoryDef(
        id="proton",
        title="Compatibility Layer (Proton)",
        subtitle="General Proton behavior toggles",
        options=(
            OptionDef("proton_log", "Enable Proton logging", "env",
                      "PROTON_LOG=1",
                      "Writes a detailed log to ~/steam-<appid>.log. Useful when a game "
                      "won't start and you need to see what Proton did."),
            OptionDef("proton_hdr", "Enable HDR passthrough", "env",
                      "PROTON_ENABLE_HDR=1",
                      "Lets the game output HDR through Proton on a properly configured "
                      "HDR display/compositor."),
            OptionDef("proton_no_esync", "Disable esync", "env",
                      "PROTON_NO_ESYNC=1",
                      "Disables the esync sync primitive. Rarely needed; useful when esync "
                      "itself is causing crashes on an older kernel/distro."),
            OptionDef("proton_no_fsync", "Disable fsync", "env",
                      "PROTON_NO_FSYNC=1",
                      "Disables the fsync sync primitive (needs a kernel with futex_waitv). "
                      "Use if fsync is suspected to cause instability."),
            OptionDef("proton_use_wined3d", "Force WineD3D instead of DXVK", "env",
                      "PROTON_USE_WINED3D=1",
                      "Falls back to Wine's OpenGL-based D3D translation instead of DXVK's "
                      "Vulkan translation. A troubleshooting option, generally slower."),
            OptionDef("proton_large_address_aware", "Force large address aware", "env",
                      "PROTON_FORCE_LARGE_ADDRESS_AWARE=1",
                      "Lets a 32-bit game address more than 2GB of RAM, if the exe supports "
                      "it. Helps some older titles that run out of memory."),
            OptionDef("proton_enable_wayland", "Use native Wayland backend", "env",
                      "PROTON_ENABLE_WAYLAND=1",
                      "Runs Proton on Wayland natively instead of through XWayland -- lower "
                      "latency and smoother frames, and the way to get HDR without gamescope. "
                      "Not feature-complete yet: can break the Steam overlay.",
                      warning="Experimental. If the mouse misbehaves or windows go borderless, also try 'Disable window decorations'; if Steam Input acts up, also try 'Disable Steam Input'."),
            OptionDef("proton_no_wm_decoration", "Disable window decorations (Wayland)", "env",
                      "PROTON_NO_WM_DECORATION=1",
                      "Troubleshooting companion for native Wayland: fixes erratic mouse "
                      "behavior/borderless window glitches some games hit with PROTON_ENABLE_WAYLAND."),
            OptionDef("proton_no_steaminput", "Disable Steam Input (Wayland)", "env",
                      "PROTON_NO_STEAMINPUT=1",
                      "Troubleshooting companion for native Wayland: fixes Steam Input acting "
                      "up with a controller under PROTON_ENABLE_WAYLAND."),
        ),
    ),

    CategoryDef(
        id="dxvk",
        title="DXVK (Direct3D → Vulkan)",
        subtitle="Tuning for the DXVK translation layer",
        options=(
            OptionDef("dxvk_async", "Async shader compilation", "env",
                      "DXVK_ASYNC=1",
                      "Compiles shaders asynchronously to reduce traversal stutter. Small "
                      "risk of a visible shader pop-in flash the first time an effect is seen."),
            OptionDef("dxvk_hud_fps", "Show DXVK HUD", "env",
                      "DXVK_HUD={mode}",
                      "Displays DXVK's lightweight built-in overlay.",
                      input=(ChoiceField("mode", (
                          ("fps", "fps"), ("frametimes", "frametimes"),
                          ("memory", "memory"), ("devinfo", "devinfo"),
                          ("full", "full (everything)"), ("none", "none (hide)"),
                      ), "fps"),)),
            OptionDef("dxvk_state_cache", "Enable shader state cache", "env",
                      "DXVK_STATE_CACHE=1",
                      "Caches pipeline state to disk so shaders don't need full recompilation "
                      "on subsequent launches. On by default in modern DXVK; explicit here for clarity."),
            OptionDef("dxvk_frame_rate", "Cap frame rate", "env",
                      "DXVK_FRAME_RATE={fps}",
                      "Simple DXVK-side FPS limiter.",
                      input=(NumberField("fps", "FPS", 30, 240, 5, 60),)),
            OptionDef("dxvk_hdr", "Enable DXVK HDR", "env",
                      "DXVK_HDR=1",
                      "Enables DXVK's HDR swapchain support, alongside PROTON_ENABLE_HDR."),
            OptionDef("dxvk_log_level", "Silence DXVK logging", "env",
                      "DXVK_LOG_LEVEL={level}",
                      "Controls how much DXVK logs to stderr.",
                      input=(ChoiceField("level", (
                          ("none", "none"), ("error", "error"), ("warn", "warn"),
                          ("info", "info"), ("debug", "debug"),
                      ), "none"),)),
            OptionDef("radv_perftest_gpl", "RADV graphics pipeline library", "env",
                      "RADV_PERFTEST=gpl",
                      "Enables RADV's graphics pipeline library path, which can reduce shader "
                      "compile stutter on AMD GPUs. Many recent Mesa versions already enable "
                      "this by default, in which case setting it explicitly is a harmless no-op.",
                      warning="May already be the default on modern Mesa -- check `mesa-git`/your distro's Mesa version before assuming it's needed."),
        ),
    ),

    CategoryDef(
        id="dlss",
        title="DLSS / NVIDIA",
        subtitle="NVIDIA-specific upscaling and driver options",
        options=(
            OptionDef("nvapi_enable", "Enable NVAPI passthrough (required for DLSS)", "env",
                      "PROTON_ENABLE_NVAPI=1",
                      "Required for DLSS to work at all under Proton. Loads dxvk-nvapi into "
                      "the prefix so the game can see it's running on an NVIDIA GPU."),
            OptionDef("nvapi_allow_other_drivers", "Allow NVAPI on non-proprietary driver", "env",
                      "DXVK_NVAPI_ALLOW_OTHER_DRIVERS=1",
                      "Needed if you're using NVK or another non-proprietary driver and still "
                      "want dxvk-nvapi to initialize."),
            OptionDef("ngx_updater", "Enable NGX (DLSS DLL) auto-updates", "env",
                      "PROTON_ENABLE_NGX_UPDATER=1",
                      "The official Valve/Proton 9+ way to keep the NVIDIA NGX/DLSS DLLs up to "
                      "date automatically. Pair with the SR/RR/FG override options below to "
                      "also force a specific render preset once the DLL is current."),
            OptionDef("proton_dlss_upgrade", "Auto-download newest DLSS DLL (GE-Proton/CachyOS)", "env",
                      "PROTON_DLSS_UPGRADE=1",
                      "Downloads and swaps in a newer nvngx_dlss DLL, and forces the latest DRS "
                      "preset -- a single-variable shortcut some community Proton builds "
                      "provide. Leave the value as '1' for latest, or edit it to a specific "
                      "version string (e.g. 310.2) to pin one. This is specific to GE-Proton "
                      "and Proton-CachyOS, not vanilla Valve Proton -- and don't combine it "
                      "with a separate dlss-swapper run, they'll conflict.",
                      warning="GE-Proton / Proton-CachyOS specific, not standard Proton. Don't combine with dlss-swapper."),
            OptionDef("proton_dlss_indicator", "Show DLSS status indicator (GE-Proton)", "env",
                      "PROTON_DLSS_INDICATOR=1",
                      "Draws an in-game indicator confirming which DLSS preset/version is "
                      "actually active -- handy for verifying the override options below "
                      "really took effect. GE-Proton specific.",
                      warning="GE-Proton specific, may not exist on other Proton builds."),
            OptionDef("nvapi_sr_override", "Enable Super Resolution preset override", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_SR_OVERRIDE=on",
                      "Must be on for the Super Resolution preset below to have any effect."),
            OptionDef("nvapi_sr_preset", "Super Resolution render preset", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_SR_OVERRIDE_RENDER_PRESET_SELECTION={preset}",
                      "Forces a specific DLSS Super Resolution model preset regardless of what "
                      "the game requests. 'Latest' tracks whatever NVIDIA currently ships as "
                      "newest (read as 'recommended' from DLSS 4.5 onward).",
                      requires="nvapi_sr_override",
                      input=(ChoiceField("preset", tuple(
                          [("render_preset_latest", "Latest / Recommended")] +
                          [(f"render_preset_{c.lower()}", f"Preset {c}") for c in "ABCDEFGHIJKLMNO"]
                      ), "render_preset_latest"),)),
            OptionDef("nvapi_rr_override", "Enable Ray Reconstruction preset override", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_RR_OVERRIDE=on",
                      "Must be on for the Ray Reconstruction preset below to have any effect."),
            OptionDef("nvapi_rr_preset", "Ray Reconstruction render preset", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_RR_OVERRIDE_RENDER_PRESET_SELECTION={preset}",
                      "Forces a specific DLSS Ray Reconstruction model preset.",
                      requires="nvapi_rr_override",
                      input=(ChoiceField("preset", tuple(
                          [("render_preset_latest", "Latest / Recommended")] +
                          [(f"render_preset_{c.lower()}", f"Preset {c}") for c in "ABCDEFGHIJKLMNO"]
                      ), "render_preset_latest"),)),
            OptionDef("nvapi_fg_override", "Enable Frame Generation preset override", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_FG_OVERRIDE=on",
                      "Must be on for the Frame Generation preset below to have any effect."),
            OptionDef("nvapi_fg_preset", "Frame Generation render preset", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSS_FG_OVERRIDE_RENDER_PRESET_SELECTION={preset}",
                      "Forces a specific DLSS Frame Generation model preset. FG has a wider "
                      "preset range (A-Z) than SR/RR.",
                      requires="nvapi_fg_override",
                      input=(ChoiceField("preset", tuple(
                          [("render_preset_latest", "Latest / Recommended"),
                           ("render_preset_default", "Default")] +
                          [(f"render_preset_{c.lower()}", f"Preset {c}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
                      ), "render_preset_latest"),)),
            OptionDef("nvapi_dlssg_mode", "Frame Generation mode", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSSG_MODE={mode}",
                      "Controls whether/how DLSS Frame Generation runs, independent of the "
                      "preset override above.",
                      input=(ChoiceField("mode", (
                          ("on", "On"), ("off", "Off"), ("auto", "Auto"),
                          ("dynamic", "Dynamic"), ("disabled", "Disabled"),
                      ), "on"),)),
            OptionDef("nvapi_dlssg_multi_frame_count", "Frame Generation multiplier", "env",
                      "DXVK_NVAPI_DRS_NGX_DLSSG_MULTI_FRAME_COUNT={n}",
                      "How many generated frames per rendered frame: 0 = app-controlled/off, "
                      "1 = 2x, 2 = 3x, 3 = 4x, 4 = 5x, 5 = 6x.",
                      input=(NumberField("n", "Multiplier (0-5)", 0, 5, 1, 1),)),
            OptionDef("gl_shader_cache", "Enable NVIDIA shader disk cache", "env",
                      "__GL_SHADER_DISK_CACHE=1",
                      "Caches compiled shaders to disk between runs on the proprietary NVIDIA "
                      "driver, reducing stutter after the first playthrough."),
            OptionDef("gl_threaded_opt", "Enable threaded optimizations", "env",
                      "__GL_THREADED_OPTIMIZATIONS=1",
                      "Lets the proprietary NVIDIA driver use an extra thread for GL command "
                      "submission. Often helps CPU-bound older titles."),
        ),
    ),

    CategoryDef(
        id="fsr",
        title="FSR (AMD FidelityFX Super Resolution)",
        subtitle="Wine/driver-level upscaling for AMD (and other) GPUs",
        options=(
            OptionDef("wine_fsr", "Enable Wine/Proton built-in FSR upscaling", "env",
                      "WINE_FULLSCREEN_FSR=1",
                      "Upscales the game's internal (lower) render resolution to your display "
                      "resolution using FSR 1.0, entirely inside Wine/Proton -- no game-side support needed."),
            OptionDef("wine_fsr_strength", "FSR sharpening strength", "env",
                      "WINE_FULLSCREEN_FSR_STRENGTH={n}",
                      "0 (max sharpen) to 5 (softest). Only applies when Wine FSR is enabled.",
                      input=(NumberField("n", "Strength", 0, 5, 1, 2),)),
            OptionDef("wine_fsr_mode", "FSR quality mode", "env",
                      "WINE_FULLSCREEN_FSR_MODE={mode}",
                      "Quality/performance tradeoff for Wine's built-in FSR.",
                      input=(ChoiceField("mode", (
                          ("ultra_quality", "Ultra Quality"), ("quality", "Quality"),
                          ("balanced", "Balanced"), ("performance", "Performance"),
                      ), "performance"),)),
            OptionDef("radv_fsr4", "Force FSR4 upscaling via RADV (experimental)", "env",
                      "RADV_FSR4_FP8=1 FSR4_UPGRADE=1",
                      "Uses Mesa's FP8 emulation to run FSR4's ML model on RADV. Requires an "
                      "RDNA3/RDNA4 GPU and a recent Mesa (often mesa-git). This is fast-moving, "
                      "driver-version-dependent territory -- double check the current variable "
                      "names for your Mesa version before relying on it.",
                      warning="Experimental / version-dependent: verify against current Mesa docs for your driver version."),
        ),
    ),

    CategoryDef(
        id=GAMESCOPE_CATEGORY_ID,
        title="Gamescope (compositor wrapper)",
        subtitle="Resolution scaling, upscaling filters, and frame limiting",
        options=(
            OptionDef(GAMESCOPE_MASTER_ID, "Wrap game in gamescope", "prefix",
                      "gamescope",
                      "Runs the game inside Valve's micro-compositor. Every option below "
                      "requires this to be checked -- gamescope's own flags always have to "
                      "sit between the literal 'gamescope' command and a closing '--' before "
                      "the wrapped game/other prefixes, so they're assembled as one block "
                      "automatically rather than placed loose in the prefix order."),
            OptionDef("gamescope_output_res", "Output resolution", "prefix",
                      "-W {w} -H {h}",
                      "Your monitor's actual resolution -- gamescope's output/display size.",
                      input=(NumberField("w", "W", 640, 7680, 10, 2560),
                             NumberField("h", "H", 480, 4320, 10, 1440)),
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_render_res", "Render resolution", "prefix",
                      "-w {w} -h {h}",
                      "What the game actually renders at internally -- the gap between this "
                      "and the output resolution above is what gets upscaled.",
                      input=(NumberField("w", "W", 640, 7680, 10, 1920),
                             NumberField("h", "H", 480, 4320, 10, 1080)),
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_filter", "Upscale filter", "prefix",
                      "-F {filter}",
                      "Which upscaler gamescope uses to go from render resolution to output "
                      "resolution.",
                      input=(ChoiceField("filter", (
                          ("fsr", "FSR 1.0"), ("nis", "NVIDIA Image Scaling"),
                      ), "fsr"),), group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_sharpness", "FSR sharpness", "prefix",
                      "--fsr-sharpness {n}",
                      "0 = maximum sharpening, 20 = minimum. Only applies with the FSR filter.",
                      input=(NumberField("n", "Sharpness", 0, 20, 1, 4),),
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_fullscreen", "Force fullscreen", "prefix",
                      "-f",
                      "Runs gamescope's window fullscreen.",
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_limiter", "Frame rate limit", "prefix",
                      "-r {fps}",
                      "Caps the frame rate gamescope will present at.",
                      input=(NumberField("fps", "FPS", 30, 240, 5, 60),),
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_hdr", "Enable HDR output", "prefix",
                      "--hdr-enabled",
                      "Passes through HDR to a gamescope session that supports it.",
                      group=GAMESCOPE_BLOCK_GROUP, requires=GAMESCOPE_MASTER_ID),
            OptionDef("gamescope_wsi", "Enable gamescope's Vulkan WSI layer", "env",
                      "ENABLE_GAMESCOPE_WSI=1",
                      "Lets Vulkan games talk to gamescope's own WSI layer directly for "
                      "correct frame pacing/latency. Recommended alongside gamescope for "
                      "Vulkan titles; independent of the prefix block above (this is a "
                      "plain env var, set whether or not gamescope wraps the process)."),
        ),
    ),

    CategoryDef(
        id="mangohud",
        title="MangoHud",
        subtitle="Performance overlay (FPS, frametime, temps, etc.)",
        options=(
            OptionDef("mangohud_enable", "Enable MangoHud", "prefix",
                      "mangohud",
                      "Wraps the game with the MangoHud overlay. Required for the sub-options "
                      "below (they configure MangoHud via MANGOHUD_CONFIG, not standalone)."),
            OptionDef("mangohud_config", "Overlay contents / layout", "env",
                      "MANGOHUD_CONFIG=fps,frametime,cpu_stats,gpu_stats,vram,ram,position=top-left",
                      "Comma-separated MangoHud config string. Edit freely -- common fields: "
                      "fps, frametime, cpu_stats, gpu_stats, vram, ram, temp, position (a corner "
                      "name), font_size (a number), background_alpha (0 to 1)."),
            OptionDef("mangohud_fps_limit", "FPS limit via MangoHud", "env",
                      "MANGOHUD_CONFIG=fps_limit={fps}",
                      "Sets a frame rate cap through MangoHud. If you also check the overlay "
                      "contents option above, merge both into one MANGOHUD_CONFIG line by hand.",
                      input=(NumberField("fps", "FPS", 0, 240, 5, 60),)),
            OptionDef("mangohud_configfile", "Use a dedicated config file", "env",
                      "MANGOHUD_CONFIGFILE=~/.config/MangoHud/thisgame.conf",
                      "Points MangoHud at a per-game config file instead of the global "
                      "~/.config/MangoHud/MangoHud.conf."),
        ),
    ),

    CategoryDef(
        id="wrappers",
        title="GameMode & Performance Wrappers",
        subtitle="System-level performance helpers",
        options=(
            OptionDef("gamemode", "Enable GameMode (prefix)", "prefix",
                      "gamemoderun",
                      "Feral Interactive's GameMode daemon: temporarily applies a performance "
                      "governor, I/O priority bump, and other tweaks while the game runs."),
            OptionDef("gamemode_env", "Enable GameMode (env var)", "env",
                      "GAMEMODE=1",
                      "Alternative way to request GameMode without wrapping the command in "
                      "gamemoderun -- some launch scripts/wrappers key off this env var "
                      "instead. Use one or the other, not both."),
            OptionDef("game_performance", "game-performance profile wrapper", "prefix",
                      "game-performance",
                      "Wraps the launch with a 'game-performance' script (shipped on Bazzite "
                      "and CachyOS via cachyos-settings) that switches to a performance power "
                      "profile via powerprofilesctl for the session, disables the screen saver, "
                      "and restores everything afterward. Only useful if that script exists on "
                      "your system, and CachyOS notes it isn't worth it on older CPUs.",
                      warning="Only present on Bazzite/CachyOS or if you've installed it yourself; skip on older CPUs per CachyOS's own guidance."),
            OptionDef("prime_run", "NVIDIA PRIME render offload", "prefix",
                      "prime-run",
                      "For hybrid Optimus laptops: runs the game on the discrete NVIDIA GPU "
                      "instead of the integrated one. Requires nvidia-prime (or equivalent) installed."),
            OptionDef("vkbasalt", "Enable vkBasalt post-processing", "env",
                      "ENABLE_VKBASALT=1",
                      "Turns on vkBasalt (CAS sharpening, SMAA, etc.) as configured in "
                      "~/.config/vkBasalt/vkBasalt.conf."),
            OptionDef("obs_vkcapture", "Enable OBS Vulkan/GL game capture", "env",
                      "OBS_VKCAPTURE=1",
                      "Lets OBS Studio (with obs-vkcapture) capture this game directly via "
                      "Vulkan/GL hooks instead of a slower screen/window capture."),
            OptionDef("mangohud_env", "Enable MangoHud (env var)", "env",
                      "MANGOHUD=1",
                      "Alternative to the mangohud prefix wrapper above -- enables the overlay "
                      "via env var instead of wrapping the command. Useful when you can't "
                      "easily prepend a wrapper (e.g. setting env vars directly in a Proton "
                      "user_settings.py). Use one or the other, not both."),
            OptionDef("force_zink", "Force Zink (OpenGL over Vulkan)", "env",
                      "MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink __GLX_VENDOR_LIBRARY_NAME=mesa",
                      "Routes OpenGL through Zink's Vulkan translation instead of a native GL "
                      "driver. Occasionally fixes or speeds up specific titles with poor native "
                      "GL support; rarely a universal win, so treat as a per-game experiment.",
                      warning="Distro-provided as the 'zink-run' script on CachyOS; a plain env var here for portability."),
        ),
    ),

    CategoryDef(
        id="wine",
        title="Wine / Prefix",
        subtitle="Prefix path, architecture, and Wine-level debug/sync options",
        options=(
            OptionDef("wineprefix", "Custom Wine prefix path", "env",
                      "WINEPREFIX=~/.wine-thisgame",
                      "Overrides where the Wine prefix lives. Steam/Proton normally manages "
                      "this for you automatically -- only set this when running through a "
                      "standalone Wine wrapper outside Proton's own compatdata handling.",
                      warning="Steam-launched Proton games already manage their own prefix; only use this for non-Proton Wine wrapper setups."),
            OptionDef("winearch", "Wine architecture", "env",
                      "WINEARCH={arch}",
                      "Forces a 32-bit or 64-bit prefix. Only relevant for a prefix you're "
                      "creating fresh.",
                      input=(ChoiceField("arch", (("win64", "64-bit"), ("win32", "32-bit")),
                                          "win64"),)),
            OptionDef("winedebug_quiet", "Silence Wine debug channels", "env",
                      "WINEDEBUG=-all",
                      "Suppresses Wine's (often very noisy) stderr debug output."),
            OptionDef("wineesync", "Enable esync", "env",
                      "WINEESYNC=1",
                      "Enables the esync sync primitive for a standalone Wine prefix (Proton "
                      "enables this itself already -- see the Proton category)."),
            OptionDef("winefsync", "Enable fsync", "env",
                      "WINEFSYNC=1",
                      "Enables the fsync sync primitive for a standalone Wine prefix."),
            OptionDef("winedlloverrides", "DLL overrides", "env",
                      "WINEDLLOVERRIDES=\"dxgi=n,b\"",
                      "Freeform DLL override string, e.g. to force native DXGI/DXVK DLLs over "
                      "Wine's built-ins for a specific component."),
            OptionDef("wine_large_address_aware", "Large address aware", "env",
                      "WINE_LARGE_ADDRESS_AWARE=1",
                      "Standalone-Wine equivalent of Proton's large-address-aware override."),
        ),
    ),

    CategoryDef(
        id="vkd3d",
        title="VKD3D-Proton (Direct3D 12)",
        subtitle="Feature toggles for the D3D12-to-Vulkan translation layer",
        options=(
            OptionDef("vkd3d_config_dxr", "Enable DXR ray tracing passthrough", "env",
                      "VKD3D_CONFIG=dxr",
                      "Lets DX12 titles that use DirectX Raytracing (DXR) run their raytracing "
                      "path through vkd3d-proton's Vulkan ray tracing translation, on GPUs/"
                      "drivers that support it."),
        ),
    ),

    CategoryDef(
        id="debugging",
        title="Debugging & Logging",
        subtitle="Diagnostic env vars for troubleshooting a game that won't start or misbehaves",
        options=(
            OptionDef("dxvk_nvapi_log_level", "DXVK-NVAPI logging", "env",
                      "DXVK_NVAPI_LOG_LEVEL={level}",
                      "'info' prints what DXVK-NVAPI is doing; 'trace' additionally logs every "
                      "entry point call (very verbose, noticeable performance hit). Anything "
                      "else is treated as no logging.",
                      input=(ChoiceField("level", (("info", "info"), ("trace", "trace")),
                                          "info"),)),
            OptionDef("vkd3d_debug", "VKD3D-Proton logging", "env",
                      "VKD3D_DEBUG={level}",
                      "Log verbosity for vkd3d-proton itself. Defaults to 'fixme' when unset.",
                      input=(ChoiceField("level", (
                          ("none", "none"), ("err", "err"), ("info", "info"),
                          ("fixme", "fixme"), ("warn", "warn"), ("trace", "trace"),
                      ), "warn"),)),
            OptionDef("vkd3d_shader_debug", "VKD3D shader compiler logging", "env",
                      "VKD3D_SHADER_DEBUG={level}",
                      "Same levels as VKD3D-Proton logging above, but for the shader compiler "
                      "specifically.",
                      input=(ChoiceField("level", (
                          ("none", "none"), ("err", "err"), ("info", "info"),
                          ("fixme", "fixme"), ("warn", "warn"), ("trace", "trace"),
                      ), "none"),)),
            OptionDef("winedebug_verbose", "Verbose Wine debug channels", "env",
                      "WINEDEBUG=+timestamp,+pid,+tid,+seh,+unwind,+threadname,+debugstr,+loaddll,+mscoree",
                      "Turns on a broad set of Wine debug channels (timestamps, thread/process "
                      "IDs, exception/unwind handling, DLL loads, .NET bootstrap) -- useful "
                      "when tracking down a crash-on-launch. Edit the channel list freely; "
                      "prefix a channel with '+' to enable or '-' to silence it."),
            OptionDef("wine_mono_trace", "Wine-Mono (.NET) exception trace filter", "env",
                      "WINE_MONO_TRACE=E:System.NotImplementedException",
                      "Wine-Mono is Wine's built-in .NET replacement, used by some game "
                      "launchers/anti-cheat stubs. This filters which exceptions get traced -- "
                      "edit the class name to catch a different exception type."),
            OptionDef("mono_log_level", "Mono runtime log level", "env",
                      "MONO_LOG_LEVEL={level}",
                      "Log verbosity for the Mono runtime itself (distinct from the Wine-Mono "
                      "trace filter above).",
                      input=(ChoiceField("level", (
                          ("error", "error"), ("critical", "critical"), ("warning", "warning"),
                          ("message", "message"), ("info", "info"), ("debug", "debug"),
                      ), "info"),)),
            OptionDef("gst_debug_no_color", "Disable GStreamer log colors", "env",
                      "GST_DEBUG_NO_COLOR=1",
                      "Strips ANSI color codes from GStreamer's debug output (used by some "
                      "engines for in-game video/movie playback) -- makes logs readable when "
                      "redirected to a file."),
        ),
    ),

    CategoryDef(
        id="engine_unreal",
        title="Engine: Unreal Engine",
        subtitle="Common -switches for UE3/UE4/UE5 titles",
        options=(
            OptionDef("ue_novid", "Skip startup splash/logos", "suffix", "-nosplash",
                      "Skips the startup logo screens some UE games show."),
            OptionDef("ue_allcores", "Use all available CPU cores", "suffix", "-USEALLAVAILABLECORES",
                      "Tells the engine to use every logical core rather than a reduced set."),
            OptionDef("ue_high_priority", "High process priority", "suffix", "-high",
                      "Launches the process at a higher OS scheduling priority."),
            OptionDef("ue_dx11", "Force DirectX 11 renderer", "suffix", "-dx11",
                      "Forces the D3D11 (via DXVK) rendering path instead of D3D12/Vulkan."),
            OptionDef("ue_dx12", "Force DirectX 12 renderer", "suffix", "-dx12",
                      "Forces the D3D12 (via DXVK/VKD3D-Proton) rendering path."),
            OptionDef("ue_vulkan", "Force native Vulkan renderer", "suffix", "-vulkan",
                      "Forces native Vulkan rendering, for the (fewer) UE titles that ship a "
                      "genuine Vulkan RHI rather than relying on D3D translation."),
            OptionDef("ue_resolution", "Set resolution", "suffix", "-ResX={w} -ResY={h}",
                      "Sets the startup render resolution.",
                      input=(NumberField("w", "W", 640, 7680, 10, 1920),
                             NumberField("h", "H", 480, 4320, 10, 1080))),
            OptionDef("ue_windowed", "Force windowed mode", "suffix", "-windowed",
                      "Starts in a window instead of fullscreen."),
            OptionDef("ue_no_vsync", "Disable VSync", "suffix", "-novsync",
                      "Disables vertical sync at the engine level."),
        ),
    ),

    CategoryDef(
        id="engine_unity",
        title="Engine: Unity",
        subtitle="Common -switches for Unity titles",
        options=(
            OptionDef("unity_force_vulkan", "Force Vulkan renderer", "suffix", "-force-vulkan",
                      "Forces Unity to use its Vulkan backend instead of the default."),
            OptionDef("unity_force_d3d11", "Force Direct3D 11 renderer", "suffix", "-force-d3d11",
                      "Forces the D3D11 (via DXVK) rendering path."),
            OptionDef("unity_force_glcore", "Force OpenGL Core renderer", "suffix", "-force-glcore",
                      "Forces Unity's desktop OpenGL Core backend."),
            OptionDef("unity_screen_fullscreen", "Fullscreen mode", "suffix", "-screen-fullscreen {mode}",
                      "Whether the game starts fullscreen or windowed.",
                      input=(ChoiceField("mode", (("1", "Fullscreen"), ("0", "Windowed")), "1"),)),
            OptionDef("unity_popup_window", "Borderless popup window", "suffix", "-popupwindow",
                      "Runs in a borderless window sized to the screen."),
            OptionDef("unity_nolog", "Disable log file", "suffix", "-nolog",
                      "Skips writing Unity's Player.log."),
            OptionDef("unity_resolution", "Set resolution", "suffix",
                      "-screen-width {w} -screen-height {h}",
                      "Sets startup window/render resolution.",
                      input=(NumberField("w", "W", 640, 7680, 10, 1920),
                             NumberField("h", "H", 480, 4320, 10, 1080))),
            OptionDef("unity_target_framerate", "Target frame rate", "suffix",
                      "-targetFrameRate {fps}",
                      "Not a universal Unity engine flag -- a common pattern several Unity "
                      "titles implement in their own command-line handling to set "
                      "Application.targetFrameRate at startup. Confirm the game actually "
                      "reads this flag before relying on it.",
                      warning="Game-specific convention, not guaranteed to exist in every Unity title.",
                      input=(NumberField("fps", "FPS", 30, 240, 10, 60),)),
        ),
    ),

    CategoryDef(
        id="engine_source",
        title="Engine: Source / GoldSrc",
        subtitle="Common -switches for Valve's Source and GoldSrc engines",
        options=(
            OptionDef("src_novid", "Skip intro video", "suffix", "-novid",
                      "Skips the Valve/studio intro video on startup."),
            OptionDef("src_console", "Enable developer console", "suffix", "-console",
                      "Opens with the developer console enabled/available."),
            OptionDef("src_high_priority", "High process priority", "suffix", "-high",
                      "Launches at a higher OS scheduling priority."),
            OptionDef("src_nojoy", "Disable joystick support", "suffix", "-nojoy",
                      "Skips joystick/gamepad initialization (can fix startup hangs on some setups)."),
            OptionDef("src_windowed", "Windowed mode", "suffix", "-windowed",
                      "Starts in a window instead of fullscreen."),
            OptionDef("src_resolution", "Set resolution", "suffix", "-w {w} -h {h}",
                      "Sets width/height.",
                      input=(NumberField("w", "W", 640, 7680, 10, 1920),
                             NumberField("h", "H", 480, 4320, 10, 1080))),
            OptionDef("src_refresh", "Set refresh rate", "suffix", "-freq {hz}",
                      "Requests a specific refresh rate.",
                      input=(NumberField("hz", "Hz", 30, 360, 1, 144),)),
        ),
    ),

    CategoryDef(
        id="engine_idtech",
        title="Engine: id Tech",
        subtitle="Common switches for id Tech 6/7 titles (Doom, Wolfenstein, etc.)",
        options=(
            OptionDef("idtech_skip_intro", "Skip intro videos", "suffix",
                      "+com_skipIntroVideo 1",
                      "Skips branding/intro videos on startup."),
            OptionDef("idtech_windowed", "Windowed mode", "suffix",
                      "+r_fullscreen 0",
                      "Starts windowed instead of fullscreen. Exact cvar varies by title -- "
                      "verify against that game's console commands.",
                      warning="id Tech titles vary more per-game than other engines -- confirm the cvar name in-game first."),
            OptionDef("idtech_custom_cvar", "Custom cvar (edit me)", "suffix",
                      "+set com_custom 1",
                      "Placeholder for a game-specific '+set cvar value' pair -- edit the value "
                      "before enabling."),
        ),
    ),

    CategoryDef(
        id="engine_godot",
        title="Engine: Godot",
        subtitle="Common --switches for Godot titles",
        options=(
            OptionDef("godot_fullscreen", "Fullscreen mode", "suffix", "--fullscreen",
                      "Starts in fullscreen."),
            OptionDef("godot_windowed", "Windowed mode", "suffix", "--windowed",
                      "Starts in a window."),
            OptionDef("godot_resolution", "Set resolution", "suffix", "--resolution {w}x{h}",
                      "Sets the window/render resolution.",
                      input=(NumberField("w", "W", 640, 7680, 10, 1920),
                             NumberField("h", "H", 480, 4320, 10, 1080))),
            OptionDef("godot_disable_vsync", "Disable VSync", "suffix", "--disable-vsync",
                      "Disables vertical sync."),
            OptionDef("godot_rendering_driver", "Rendering driver", "suffix",
                      "--rendering-driver {driver}",
                      "Which rendering backend Godot starts with.",
                      input=(ChoiceField("driver", (("vulkan", "Vulkan"), ("opengl3", "OpenGL 3")),
                                          "vulkan"),)),
        ),
    ),
]


def all_option_ids() -> set:
    return {opt.id for cat in CATALOG for opt in cat.options}


def find_option(option_id: str) -> OptionDef | None:
    for cat in CATALOG:
        for opt in cat.options:
            if opt.id == option_id:
                return opt
    return None


def find_category(category_id: str) -> CategoryDef | None:
    for cat in CATALOG:
        if cat.id == category_id:
            return cat
    return None
