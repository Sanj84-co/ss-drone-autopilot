import asyncio
from pymavlink.dialects.v20 import common

from utils.drone import Drone
from utils.mission import Mission
from utils.takeoff import takeoff, return_to_launch
from utils.logger import log_system, log_success, log_fail, bcolors
from utils.speed import change_speed
import utils.mode as mode

from helper.file_reader import read_waypoints
from helper.airdrop import Airdrop
from helper.math_funcs import haversine_distance

IMAGING_ALTITUDE  = 20   # meters AGL during imaging lap
DROP_ALTITUDE     = 10   # meters AGL when making the airdrop pass
APPROACH_SPEED    = 8    # m/s during imaging lap (slow for camera)
DROP_SPEED        = 5    # m/s when approaching drop point (precise)
DROP_RADIUS_M     = 3.0  # meters — how close to target center before dropping


class TargetLocalization:
    '''
    Handles the airdrop task for Soaring Skies:
      1. Fly an imaging lap over the search boundary waypoints.
      2. Wait for the imaging system to identify the correct target and provide its GPS coordinates.
      3. Fly to the target and autonomously release the payload.

    IMAGING INTERFACE
    -----------------
    The imaging team calls:
        await target_loc.set_target(lat, long)
    ...once they have identified the correct target. This unblocks the mission
    and allows the drone to proceed to the drop.

    If no target is received within `imaging_timeout` seconds, the mission aborts.
    '''

    def __init__(self, drone: Drone, searchBoundaryFile: str = None,
                 imaging_timeout: float = 120.0):
        self.drone = drone
        self.searchBoundaryFile = searchBoundaryFile
        self.imaging_timeout = imaging_timeout

        self.airdrop = Airdrop(drone)
        self.mission_handler = Mission(drone=drone)

        # Imaging interface — imaging team calls set_target() to provide coords
        self._target_event = asyncio.Event()
        self._target_coords: list | None = None   # [lat_deg, long_deg]

    # ------------------------------------------------------------------
    # PUBLIC IMAGING INTERFACE
    # ------------------------------------------------------------------

    async def set_target(self, lat: float, long: float):
        '''
        Called by the imaging system once the correct target is identified.
        lat/long should be in decimal degrees.
        '''
        self._target_coords = [lat, long]
        self._target_event.set()
        log_success(msgname="Target Localization",
                    msg=f"Target received from imaging: lat={lat:.7f}, long={long:.7f}")

    # ------------------------------------------------------------------
    # MAIN MISSION
    # ------------------------------------------------------------------

    async def run(self, waypointsFile: str = None, rtl: bool = True):
        '''
        Full airdrop mission:
          1. Arm airdrop mechanism
          2. Takeoff
          3. Fly imaging lap (slow, low)
          4. Wait for imaging to return target coords
          5. Fly to target and drop
          6. RTL
        '''
        wf = waypointsFile or self.searchBoundaryFile
        if not wf:
            log_fail(msgname="Target Localization", msg="No search boundary file provided.")
            return

        log_system(msgname="Target Localization", msg="=== AIRDROP MISSION START ===", color=bcolors.HEADER)

        # Step 1: Arm the drop mechanism before takeoff
        await self.airdrop.arm_airdrop()

        # Step 2: Takeoff to imaging altitude
        await takeoff(self.drone, target_alt=IMAGING_ALTITUDE)

        # Step 3: Set approach speed and fly imaging lap
        await change_speed(self.drone, speed=APPROACH_SPEED)
        await self._fly_imaging_lap(wf)

        # Step 4: Wait for imaging to give us the target
        target = await self._wait_for_target()
        if target is None:
            log_fail(msgname="Target Localization",
                     msg="Imaging timeout — no target received. Aborting airdrop.")
            if rtl:
                await return_to_launch(self.drone)
            return

        # Step 5: Fly to target and drop
        await self._fly_to_target_and_drop(target)

        # Step 6: RTL
        if rtl:
            log_system(msgname="Target Localization", msg="Airdrop complete. Returning to launch.")
            await return_to_launch(self.drone)

        log_success(msgname="Target Localization", msg="=== AIRDROP MISSION COMPLETE ===")

    # ------------------------------------------------------------------
    # IMAGING LAP
    # ------------------------------------------------------------------

    async def _fly_imaging_lap(self, waypointsFile: str):
        '''
        Uploads and flies a waypoint mission over the search boundary so the
        imaging system can capture all targets.
        '''
        log_system(msgname="Target Localization", msg="Beginning imaging lap over search area...")
        waypoints = read_waypoints(waypointsFile)

        # Override altitude to imaging altitude
        waypoints = [[wp[0], wp[1], IMAGING_ALTITUDE] for wp in waypoints]

        await self.mission_handler.upload_mission(
            waypoints=waypoints,
            rtl=False,
            begin_immediately=True
        )
        log_success(msgname="Target Localization", msg="Imaging lap complete.")

    # ------------------------------------------------------------------
    # WAIT FOR TARGET
    # ------------------------------------------------------------------

    async def _wait_for_target(self) -> list | None:
        '''
        Waits for the imaging team to call set_target().
        Returns [lat, long] if received before timeout, None otherwise.
        Drone loiters while waiting.
        '''
        log_system(msgname="Target Localization",
                   msg=f"Loitering — waiting for imaging target (timeout: {self.imaging_timeout}s)...",
                   color=bcolors.OKCYAN)
        await mode.set_mode(self.drone, mode.LOITER)

        try:
            await asyncio.wait_for(self._target_event.wait(), timeout=self.imaging_timeout)
            return self._target_coords
        except asyncio.TimeoutError:
            return None

    # ------------------------------------------------------------------
    # FLY TO TARGET AND DROP
    # ------------------------------------------------------------------

    async def _fly_to_target_and_drop(self, target: list):
        '''
        Flies to the identified target at drop altitude and releases the payload
        once within DROP_RADIUS_M meters of the target center.
        '''
        lat, long = target
        log_system(msgname="Target Localization",
                   msg=f"Flying to drop target: lat={lat:.7f}, long={long:.7f} at {DROP_ALTITUDE}m",
                   color=bcolors.OKCYAN)

        # Descend to drop altitude while flying to target
        await change_speed(self.drone, speed=DROP_SPEED)

        # Upload single-waypoint mission to the target at drop altitude
        drop_waypoint = [[lat, long, DROP_ALTITUDE]]
        await self.mission_handler.upload_mission(
            waypoints=drop_waypoint,
            rtl=False,
            begin_immediately=True
        )

        # Wait until we're close enough to the target, then drop
        await self._wait_and_drop(lat, long)

    async def _wait_and_drop(self, target_lat: float, target_long: float):
        '''
        Polls current position. When within DROP_RADIUS_M of the target, triggers release.
        '''
        log_system(msgname="Target Localization",
                   msg=f"Approaching target. Will drop within {DROP_RADIUS_M}m...")
        while True:
            pos = await self.drone.get_position_deg()
            current = [pos['lat'] / 1e7, pos['long'] / 1e7, pos['alt']]
            target  = [target_lat, target_long, DROP_ALTITUDE]
            dist = haversine_distance(current, target)

            log_system(msgname="Target Localization",
                       msg=f"Distance to target: {dist:.2f}m")

            if dist <= DROP_RADIUS_M:
                log_system(msgname="Target Localization",
                           msg=f"Within {DROP_RADIUS_M}m of target — DROPPING PAYLOAD",
                           color=bcolors.FAIL)
                await self.airdrop.release()
                return

            await asyncio.sleep(0.5)
