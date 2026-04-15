'''
SITL TEST SCRIPT — Soaring Skies Full Mission
==============================================
Run this instead of main_ss.py when testing in the ArduPilot SITL simulator.

It does everything main_ss.py does, PLUS:
  - Prints a live status dashboard every 2 seconds
  - Simulates the imaging team calling set_target() after a delay
  - Logs lap times and airdrop result to a file (sitl_test_results.txt)
  - Has a --dry-run flag to test mission upload without arming/flying

Usage:
    python test_sitl.py              # full mission sim
    python test_sitl.py --dry-run    # upload only, no flight
'''

import asyncio
import argparse
import time
import os
import sys

from utils.drone import Drone
from utils.logger import log_system, log_success, log_fail, bcolors
from utils.geofence import Geofence

from missions.soaringskiesmission import SoaringSkiesMission, ORDER_TIME_TRIAL_FIRST

# -----------------------------------------------------------------------
# SITL CONFIG
# -----------------------------------------------------------------------

# These match ArduPilot SITL defaults — no changes needed if running locally
SITL_CONNECTION  = 'tcp:127.0.0.1:5763'

# Fake target coords — simulates imaging team identifying the correct target
# Uses Search Boundary 1 (center-ish of the search area) from Coordinates.xlsx
SIMULATED_TARGET_LAT  = 40.5448415459701
SIMULATED_TARGET_LONG = -74.46580592011446

# How long to wait before "imaging" sends the target (seconds)
# In real life imaging would call set_target() when they see the target
IMAGING_SIM_DELAY = 20.0

# Output file for test results
RESULTS_FILE = 'sitl_test_results.txt'

# -----------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------

async def simulate_imaging(mission: SoaringSkiesMission, delay: float):
    '''
    Simulates the imaging team detecting the target after a delay.
    In real usage, imaging calls: await mission.target_loc.set_target(lat, long)
    '''
    log_system(msgname="[SITL] Imaging Sim",
               msg=f"Imaging system will report target in {delay:.0f}s...",
               color=bcolors.OKCYAN)
    await asyncio.sleep(delay)
    log_system(msgname="[SITL] Imaging Sim",
               msg=f"Target identified! Sending coords to autopilot: ({SIMULATED_TARGET_LAT}, {SIMULATED_TARGET_LONG})",
               color=bcolors.OKGREEN)
    await mission.target_loc.set_target(SIMULATED_TARGET_LAT, SIMULATED_TARGET_LONG)


async def status_dashboard(drone: Drone, mission: SoaringSkiesMission):
    '''Prints a live status readout every 2 seconds during the flight.'''
    await asyncio.sleep(3)  # let things initialize first
    while True:
        try:
            pos = await drone.get_position_deg()
            lat  = pos['lat'] / 1e7
            long = pos['long'] / 1e7
            alt  = pos['alt']

            elapsed = time.perf_counter() - mission._flight_start if mission._flight_start else 0
            remaining = max(0, mission.FLIGHT_TIME_LIMIT - elapsed)

            lap_info = f"Laps: {len(mission.lap_times)}/3" if mission.lap_times else "Laps: 0/3"
            drop_info = "DROP: ✓" if mission.airdrop_success else "DROP: pending"

            print(
                f"\n{bcolors.BOLD}{'─'*55}{bcolors.ENDC}\n"
                f"  {bcolors.OKCYAN}[SITL STATUS]{bcolors.ENDC}\n"
                f"  Position : {lat:.6f}, {long:.6f}  Alt: {alt:.1f}m\n"
                f"  Time     : {elapsed:.0f}s elapsed | {remaining:.0f}s remaining\n"
                f"  {lap_info}  |  {drop_info}\n"
                f"{bcolors.BOLD}{'─'*55}{bcolors.ENDC}"
            )
        except Exception:
            pass  # drone not ready yet
        await asyncio.sleep(2)


def write_results(mission: SoaringSkiesMission):
    '''Writes test results to a file after the mission ends.'''
    elapsed = time.perf_counter() - mission._flight_start if mission._flight_start else 0
    lines = [
        "=" * 50,
        "SOARING SKIES SITL TEST RESULTS",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 50,
        "",
        f"Total flight time : {elapsed:.1f}s",
        "",
        "--- Time Trial ---",
    ]
    if mission.lap_times:
        for i, t in enumerate(mission.lap_times, 1):
            lines.append(f"  Lap {i}: {t:.2f}s")
        lines.append(f"  Best lap: {min(mission.lap_times):.2f}s")
    else:
        lines.append("  No lap times recorded.")

    lines += [
        "",
        "--- Airdrop ---",
        f"  Payload dropped: {'YES' if mission.airdrop_success else 'NO'}",
        "",
    ]

    with open(RESULTS_FILE, 'w') as f:
        f.write('\n'.join(lines))

    log_success(msgname="[SITL]", msg=f"Results written to {RESULTS_FILE}")
    print('\n'.join(lines))


# -----------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------

async def main(dry_run: bool = False):
    log_system(msgname="[SITL]",
               msg="=== SOARING SKIES SITL TEST STARTING ===",
               color=bcolors.HEADER)

    if dry_run:
        log_system(msgname="[SITL]", msg="DRY RUN MODE — mission will upload but drone will NOT arm or fly.",
                   color=bcolors.YELLOW)

    # Connect drone
    drone = Drone()
    drone.initialize_drone(
        parametersFile='info_files/ss_settings.txt',
        configFile='info_files/ss_sitl_config.txt'   # uses SITL connection string
    )

    # Geofence
    fence = Geofence(drone=drone, geofenceFile='info_files/ss_geofence.txt')

    # Mission
    mission = SoaringSkiesMission(
        drone=drone,
        circuitFile='info_files/ss_circuit_waypoints.txt',
        searchBoundaryFile='info_files/ss_search_boundary.txt',
        order=ORDER_TIME_TRIAL_FIRST
    )

    if dry_run:
        # Just test that everything connects and uploads without flying
        await asyncio.gather(
            drone.start_background_processes(),
            drone.watch_for_heartbeat(),
            fence.upload_fence(),
            dry_run_test(drone, mission)
        )
        return

    # Full flight + imaging simulation running concurrently
    try:
        await asyncio.gather(
            drone.start_background_processes(),
            drone.watch_for_heartbeat(),
            fence.upload_fence(),
            mission.run(),
            simulate_imaging(mission, delay=IMAGING_SIM_DELAY),
            status_dashboard(drone, mission),
        )
    except Exception as e:
        log_fail(msgname="[SITL]", msg=f"Mission ended with error: {e}")
    finally:
        write_results(mission)


async def dry_run_test(drone: Drone, mission: SoaringSkiesMission):
    '''Dry run: just waits for connection then prints success.'''
    from utils.mission import Mission
    from helper.file_reader import read_waypoints

    log_system(msgname="[SITL DRY RUN]", msg="Waiting for drone connection...")
    await drone.message_stream_exists(msgname="[SITL DRY RUN]", msg="Waiting for message stream...")
    await asyncio.sleep(2)

    log_system(msgname="[SITL DRY RUN]", msg="Testing waypoint file read...")
    wps = read_waypoints('info_files/ss_circuit_waypoints.txt')
    log_success(msgname="[SITL DRY RUN]", msg=f"Circuit waypoints loaded: {len(wps)} points")

    wps2 = read_waypoints('info_files/ss_search_boundary.txt')
    log_success(msgname="[SITL DRY RUN]", msg=f"Search boundary loaded: {len(wps2)} points")

    log_system(msgname="[SITL DRY RUN]", msg="Testing airdrop arm...")
    await mission.airdrop.arm_airdrop()
    log_success(msgname="[SITL DRY RUN]", msg="Airdrop arm OK")

    log_success(msgname="[SITL DRY RUN]", msg="=== DRY RUN COMPLETE — all systems OK ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Soaring Skies SITL Test")
    parser.add_argument('--dry-run', action='store_true',
                        help='Test connection and file reads without arming or flying')
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
