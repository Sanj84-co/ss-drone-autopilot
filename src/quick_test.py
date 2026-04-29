import asyncio
from utils.drone import Drone
from utils.logger import log_system
from missions.soaringskiesmission import SoaringSkiesMission, ORDER_TIME_TRIAL_FIRST

async def main():
    drone = Drone()
    drone.initialize_drone(
        parametersFile='info_files/ss_settings.txt',
        configFile='info_files/ss_sitl_config.txt'
    )
    
    mission = SoaringSkiesMission(
        drone=drone,
        circuitFile='info_files/ss_circuit_waypoints.txt',
        searchBoundaryFile='info_files/ss_search_boundary.txt',
        order=ORDER_TIME_TRIAL_FIRST
    )

    await asyncio.gather(
        drone.start_background_processes(),
        drone.watch_for_heartbeat(),
        mission.run(),
        simulate_imaging(mission)
    )

async def simulate_imaging(mission):
    await asyncio.sleep(20)
    await mission.target_loc.set_target(40.5448415459701, -74.46580592011446)

if __name__ == "__main__":
    asyncio.run(main())
