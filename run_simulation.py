
from pathlib import Path
import re
import subprocess


# ============================================================
# Simulation settings
# ============================================================

NEXUS_DIR = Path.home() / "installations" / "nexus"

# Use the NEXUS executable that you rebuilt and installed.
NEXUS_EXE = (
    Path.home()
    / "installations"
    / "nexus-installation"
    / "bin"
    / "nexus"
)

INIT_MACRO = NEXUS_DIR / "macros" / "miniarapuca.test.init.mac"

GENERATOR_MACRO = (
    NEXUS_DIR
    / "macros"
    / "generators"
    / "MonochromaticBeam_ARAPUCA.mac"
)

CONFIG_MACRO = NEXUS_DIR / "macros" / "miniarapuca.config.test.mac"

OUTPUT_DIR = (
    NEXUS_DIR
    / "output"
    / "MiniArapucaStudies"
    / "PositionScan"
)

WAVELENGTHS = [110, 120, 130, 140, 150,
               ]#160, 170, 180, 190, 200]

N_PHOTONS = 100_000


# ============================================================
# Beam positions (coordinates in mm)
# ============================================================
# Assumption: negative z is the lower side in your geometry.

POSITIONS = {
    "Pos1": ( -30.0, -30.0),
    "Pos2": ( -30.0,  0.0),
    "Pos3": ( -30.0, 30.0),
}


# ============================================================
# Helpers
# ============================================================

def set_macro_value(text, command, value):
    """
    Replace exactly one Geant4 macro command, preserving
    the command name and formatting.
    """
    pattern = rf"^(\s*{re.escape(command)}\s+).*$"

    updated, count = re.subn(
        pattern,
        lambda match: f"{match.group(1)}{value}",
        text,
        flags=re.MULTILINE,
    )

    if count != 1:
        raise ValueError(
            f"Expected exactly one occurrence of {command!r}, "
            f"but found {count}."
        )

    return updated


# ============================================================
# Validate inputs
# ============================================================

for path in [
    INIT_MACRO,
    GENERATOR_MACRO,
    CONFIG_MACRO,
    NEXUS_EXE,
]:
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Save original macros
# ============================================================

original_generator = GENERATOR_MACRO.read_text()
original_config = CONFIG_MACRO.read_text()

total_runs = len(POSITIONS) * len(WAVELENGTHS)
run_number = 0


try:
    for position_name, (x_mm, z_mm) in POSITIONS.items():

        # One output folder per beam position
        position_output_dir = OUTPUT_DIR / position_name
        position_output_dir.mkdir(parents=True, exist_ok=True)

        print("\n" + "#" * 65)
        print(f"{position_name}: gen_x = {x_mm:+.1f} mm, "
              f"gen_z = {z_mm:+.1f} mm")
        print("#" * 65)

        for wavelength in WAVELENGTHS:

            run_number += 1

            print(
                f"\n[{run_number}/{total_runs}] "
                f"{position_name}, {wavelength} nm, "
                f"{N_PHOTONS:,} photons",
                flush=True,
            )

            # ------------------------------------------------
            # Configure wavelength
            # ------------------------------------------------

            generator = set_macro_value(
                original_generator,
                "/Generator/MonochromaticBeam/wavelength_mean",
                f"{wavelength}. nm",
            )

            # ------------------------------------------------
            # Configure beam position
            # Always start from the original config macro
            # ------------------------------------------------

            config = set_macro_value(
                original_config,
                "/Geometry/XArapuca/gen_x",
                f"{x_mm:.3f} mm",
            )

            config = set_macro_value(
                config,
                "/Geometry/XArapuca/gen_z",
                f"{z_mm:.3f} mm",
            )

            # ------------------------------------------------
            # Configure output filename
            # NEXUS will normally append .h5
            # ------------------------------------------------

            output_file = (
                position_output_dir / f"arapuca_{wavelength}nm"
            )

            config = set_macro_value(
                config,
                "/nexus/persistency/output_file",
                str(output_file),
            )

            # Write macros for this run
            GENERATOR_MACRO.write_text(generator)
            CONFIG_MACRO.write_text(config)

            # ------------------------------------------------
            # Run NEXUS
            # Run from the repository root so relative macro
            # paths in the initialization macro resolve.
            # ------------------------------------------------

            result = subprocess.run(
                [
                    str(NEXUS_EXE),
                    "-n",
                    str(N_PHOTONS),
                    str(INIT_MACRO),
                ],
                cwd=NEXUS_DIR,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"NEXUS failed for {position_name}, "
                    f"{wavelength} nm "
                    f"(return code {result.returncode})."
                )

            # ------------------------------------------------
            # Verify output
            # ------------------------------------------------

            expected_file = Path(str(output_file) + ".h5")

            if expected_file.is_file():
                print(f"Saved: {expected_file}", flush=True)
            else:
                raise FileNotFoundError(
                    f"NEXUS returned successfully, but the expected "
                    f"output file was not found: {expected_file}"
                )

finally:
    # Restore both macros even if a simulation fails.
    GENERATOR_MACRO.write_text(original_generator)
    CONFIG_MACRO.write_text(original_config)

    print("\nOriginal generator and configuration macros restored.")


print("\nAll position scans completed successfully.")
print(f"Output directory: {OUTPUT_DIR}")
