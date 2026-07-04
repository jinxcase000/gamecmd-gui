"""
options_catalog.py

A data-driven catalog of commonly used Linux/Steam gaming launch options,
grouped into categories. Each Option becomes a checkbox + editable value in
the Game Editor UI. Checking the box includes the (possibly edited) value
in the profile's env_vars / prefix / suffix string.

target values map directly onto the three fields gamecmd's games.yaml
supports:
    "env"    -> env_vars   (must look like KEY=VALUE)
    "prefix" -> prefix     (a command / wrapper, executed before the game)
    "suffix" -> suffix     (an argument passed after the game binary)

NOTE ON ACCURACY: values here reflect widely-documented, real flags/env
vars for Proton/DXVK/Wine/gamescope/MangoHud and common engines. A few
(marked with `warning=`) are new, driver-version-dependent, or need
verification per-game -- the UI surfaces those warnings rather than
hiding the uncertainty.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OptionDef:
    id: str
    label: str
    target: str  # "env" | "prefix" | "suffix"
    default: str
    description: str
    warning: str = ""


@dataclass(frozen=True)
class CategoryDef:
    id: str
    title: str
    subtitle: str
    options: tuple  # tuple[OptionDef, ...]


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
                      "DXVK_HUD=fps",
                      "Displays DXVK's lightweight built-in overlay. Edit the value: fps, "
                      "frametimes, memory, devinfo, or 'full' for everything."),
            OptionDef("dxvk_state_cache", "Enable shader state cache", "env",
                      "DXVK_STATE_CACHE=1",
                      "Caches pipeline state to disk so shaders don't need full recompilation "
                      "on subsequent launches. On by default in modern DXVK; explicit here for clarity."),
            OptionDef("dxvk_frame_rate", "Cap frame rate", "env",
                      "DXVK_FRAME_RATE=60",
                      "Simple DXVK-side FPS limiter. Edit the number to your target FPS."),
            OptionDef("dxvk_hdr", "Enable DXVK HDR", "env",
                      "DXVK_HDR=1",
                      "Enables DXVK's HDR swapchain support, alongside PROTON_ENABLE_HDR."),
            OptionDef("dxvk_log_level", "Silence DXVK logging", "env",
                      "DXVK_LOG_LEVEL=none",
                      "Suppresses DXVK's log output. Useful once a game is confirmed working "
                      "and you don't need the log noise."),
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
                      "Lets Proton keep the NVIDIA NGX/DLSS DLLs up to date automatically."),
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
                      "WINE_FULLSCREEN_FSR_STRENGTH=2",
                      "Sharpening strength, 0 (max sharpen) to 5 (softest). Only applies "
                      "when Wine FSR is enabled."),
            OptionDef("wine_fsr_mode", "FSR quality mode", "env",
                      "WINE_FULLSCREEN_FSR_MODE=performance",
                      "Edit the value: ultra_quality, quality, balanced, or performance."),
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
        id="gamescope",
        title="Gamescope (compositor wrapper)",
        subtitle="Resolution scaling, upscaling filters, and frame limiting",
        options=(
            OptionDef("gamescope_basic", "Wrap game in gamescope", "prefix",
                      "gamescope --",
                      "Runs the game inside Valve's micro-compositor. Required for the other "
                      "gamescope options below to have any effect. Keep this as the outermost "
                      "(topmost) prefix entry."),
            OptionDef("gamescope_res", "Set output/render resolution", "prefix",
                      "-W 2560 -H 1440 -w 1920 -h 1080",
                      "Output res (-W/-H, your monitor) vs. internal render res (-w/-h, what "
                      "the game actually renders at) -- the gap between them is what gets upscaled."),
            OptionDef("gamescope_fsr", "Upscale filter: FSR", "prefix",
                      "-F fsr",
                      "Use FSR 1.0 to upscale from render resolution to output resolution."),
            OptionDef("gamescope_nis", "Upscale filter: NIS", "prefix",
                      "-F nis",
                      "Use NVIDIA Image Scaling instead of FSR for the upscale filter."),
            OptionDef("gamescope_sharpness", "FSR sharpness", "prefix",
                      "--fsr-sharpness 4",
                      "0 = maximum sharpening, 20 = minimum. Only applies with -F fsr."),
            OptionDef("gamescope_fullscreen", "Force fullscreen", "prefix",
                      "-f",
                      "Runs gamescope's window fullscreen."),
            OptionDef("gamescope_limiter", "Frame rate limit", "prefix",
                      "-r 60",
                      "Caps the frame rate gamescope will present at."),
            OptionDef("gamescope_hdr", "Enable HDR output", "prefix",
                      "--hdr-enabled",
                      "Passes through HDR to a gamescope session that supports it."),
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
                      "fps, frametime, cpu_stats, gpu_stats, vram, ram, temp, position=<corner>, "
                      "font_size=<n>, background_alpha=<0-1>."),
            OptionDef("mangohud_fps_limit", "FPS limit via MangoHud", "env",
                      "MANGOHUD_CONFIG=fps_limit=60",
                      "Sets a frame rate cap through MangoHud. If you also check the overlay "
                      "contents option above, merge both into one MANGOHUD_CONFIG line by hand."),
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
            OptionDef("gamemode", "Enable GameMode", "prefix",
                      "gamemoderun",
                      "Feral Interactive's GameMode daemon: temporarily applies a performance "
                      "governor, I/O priority bump, and other tweaks while the game runs."),
            OptionDef("game_performance", "Bazzite-style performance profile wrapper", "prefix",
                      "game-performance",
                      "Wraps the launch with a 'game-performance' script (as shipped on Bazzite "
                      "and similar distros) that switches to a performance power profile for "
                      "the session and restores it afterward. Only useful if that script exists "
                      "on your system.",
                      warning="Only present on Bazzite/ChimeraOS-derived distros or if you've installed it yourself."),
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
                      "WINEARCH=win64",
                      "Forces a 32-bit (win32) or 64-bit (win64) prefix. Only relevant for a "
                      "prefix you're creating fresh."),
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
            OptionDef("ue_resolution", "Set resolution", "suffix", "-ResX=1920 -ResY=1080",
                      "Sets the startup render resolution."),
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
            OptionDef("unity_screen_fullscreen", "Fullscreen mode", "suffix", "-screen-fullscreen 1",
                      "1 = fullscreen, 0 = windowed."),
            OptionDef("unity_popup_window", "Borderless popup window", "suffix", "-popupwindow",
                      "Runs in a borderless window sized to the screen."),
            OptionDef("unity_nolog", "Disable log file", "suffix", "-nolog",
                      "Skips writing Unity's Player.log."),
            OptionDef("unity_resolution", "Set resolution", "suffix",
                      "-screen-width 1920 -screen-height 1080",
                      "Sets startup window/render resolution."),
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
            OptionDef("src_resolution", "Set resolution", "suffix", "-w 1920 -h 1080",
                      "Sets width/height."),
            OptionDef("src_refresh", "Set refresh rate", "suffix", "-freq 144",
                      "Requests a specific refresh rate."),
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
            OptionDef("godot_resolution", "Set resolution", "suffix", "--resolution 1920x1080",
                      "Sets the window/render resolution."),
            OptionDef("godot_disable_vsync", "Disable VSync", "suffix", "--disable-vsync",
                      "Disables vertical sync."),
            OptionDef("godot_rendering_driver", "Rendering driver", "suffix",
                      "--rendering-driver vulkan",
                      "Edit the value: vulkan, opengl3, etc."),
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
