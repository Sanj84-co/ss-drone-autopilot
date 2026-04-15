import asyncio

from utils.drone import Drone
from utils.logger import log_system
from utils.geofence import Geofence

from helper.file_reader import read_config_file

from missions.soaringskiesmission import SoaringSkiesMission, ORDER_TIME_TRIAL_FIRST, ORDER_AIRDROP_FIRST


async def main():
    # --- Connect & configure drone ---
    drone = Drone()
    drone.initialize_drone(
        parametersFile='info_files/ss_settings.txt',
        configFile='info_files/ss_config.txt'
    )

    # --- Upload geofence ---
    fence = Geofence(drone=drone, geofenceFile='info_files/ss_geofence.txt')

    # --- Build the full competition mission ---
    # Change order to ORDER_AIRDROP_FIRST if you want to do airdrop first.
    # This MUST be declared verbally before flight per the rules.
    mission = SoaringSkiesMission(
        drone=drone,
        circuitFile='info_files/ss_circuit_waypoints.txt',
        searchBoundaryFile='info_files/ss_search_boundary.txt',
        order=ORDER_TIME_TRIAL_FIRST
    )

    # --- Run everything concurrently ---
    await asyncio.gather(
        drone.start_background_processes(),
        drone.watch_for_heartbeat(),
        fence.upload_fence(),
        mission.run()
    )

    # NOTE: To provide the imaging target during flight, your imaging script calls:
    #   await mission.target_loc.set_target(lat, long)
    # This unblocks the airdrop and sends the drone to the correct target.


if __name__ == "__main__":
    asyncio.run(main())
