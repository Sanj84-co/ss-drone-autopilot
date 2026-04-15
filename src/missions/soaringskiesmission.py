import asyncio
import time
from pymavlink.dialects.v20 import common

from utils.drone import Drone
from utils.mission import Mission
from utils.takeoff import takeoff, return_to_launch
from utils.armdisarm import arm_drone
from utils.logger import log_system, log_success, log_fail, bcolors
from utils.speed import change_speed
import utils.mode as mode

from helper.file_reader import read_waypoints
from helper.airdrop import Airdrop

from missions.targetlocalization import TargetLocalization
from missions.circuittimetrial import CircuitTimeTrial


# Mission order options
ORDER_TIME_TRIAL_FIRST  = "time_trial_first"
ORDER_AIRDROP_FIRST     = "airdrop_first"


class SoaringSkiesMission:
    '''
    Full Soaring Skies flight demonstration:
      - Task A: Circuit Time Trial (3 laps, best lap time recorded)
      - Task B: Target ID & Airdrop (imaging lap + autonomous payload drop)

    Both tasks are completed in a single 20-minute flight window.
    The order (time trial first vs airdrop first) must be declared before flight
    and is set via the `order` parameter.

    Usage:
        mission = SoaringSkiesMission(
            drone=drone,
            circuitFile='info_files/ss_circuit_waypoints.txt',
            searchBoundaryFile='info_files/ss_search_boundary.txt',
            order=ORDER_TIME_TRIAL_FIRST
        )
        await mission.run()

    Imaging Interface:
        Once imaging identifies the target, call:
            await mission.target_loc.set_target(lat, long)
    '''

    FLIGHT_TIME_LIMIT = 20 * 60   # 20 minutes in seconds
    TIMEOUT_BUFFER    = 60        # stop new tasks if < 60s remaining

    def __init__(self, drone: Drone,
                 circuitFile: str = None,
                 searchBoundaryFile: str = None,
                 order: str = ORDER_TIME_TRIAL_FIRST):

        self.drone              = drone
        self.circuitFile        = circuitFile
        self.searchBoundaryFile = searchBoundaryFile
        self.order              = order

        self.time_trial  = CircuitTimeTrial(drone=drone, waypointsFile=circuitFile)
        self.target_loc  = TargetLocalization(drone=drone, searchBoundaryFile=searchBoundaryFile)
        self.airdrop     = self.target_loc.airdrop  # expose for servo testing

        self._flight_start: float | None = None
        self.lap_times: list[float] = []
        self.airdrop_success = False

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------

    async def run(self):
        '''
        Runs the full Soaring Skies demonstration flight.
        '''
        log_system(msgname="Soaring Skies", msg="=== SOARING SKIES COMPETITION FLIGHT START ===",
                   color=bcolors.HEADER)

        self._flight_start = time.perf_counter()

        # Arm airdrop before anything else (safety)
        await self.airdrop.arm_airdrop()

        # Takeoff
        await takeoff(self.drone, target_alt=self.drone.target_alt)

        # Run tasks in declared order
        if self.order == ORDER_TIME_TRIAL_FIRST:
            await self._run_time_trial()
            if self._time_remaining() > self.TIMEOUT_BUFFER:
                await self._run_airdrop()
            else:
                log_fail(msgname="Soaring Skies",
                         msg="Not enough time remaining for airdrop task.")
        else:
            await self._run_airdrop()
            if self._time_remaining() > self.TIMEOUT_BUFFER:
                await self._run_time_trial()
            else:
                log_fail(msgname="Soaring Skies",
                         msg="Not enough time remaining for time trial task.")

        # RTL
        log_system(msgname="Soaring Skies", msg="All tasks complete. Returning to launch.")
        await return_to_launch(self.drone)

        self._print_summary()

    # ------------------------------------------------------------------
    # TASK A: TIME TRIAL
    # ------------------------------------------------------------------

    async def _run_time_trial(self):
        log_system(msgname="Soaring Skies",
                   msg="--- Starting Task A: Circuit Time Trial ---",
                   color=bcolors.OKCYAN)

        if not self.circuitFile:
            log_fail(msgname="Soaring Skies", msg="No circuit waypoints file provided. Skipping time trial.")
            return

        waypoints = read_waypoints(self.circuitFile)
        home_pos  = await self.drone.get_home_position_deg()

        # Append home as the lap closing waypoint
        waypoints.append([home_pos['lat'], home_pos['long'], self.drone.target_alt])

        mission_handler = Mission(drone=self.drone)
        await mission_handler.upload_mission(waypoints=waypoints, rtl=False, begin_immediately=False)

        best_time = float('inf')
        total_time = 0.0

        for lap in range(1, 4):
            if lap == 1:
                await mission_handler.begin_mission(rtl=False)
            else:
                # Re-run from waypoint 1 (skip takeoff item at index 0)
                await self.drone.send_command(
                    command=common.MAV_CMD_DO_SET_MISSION_CURRENT, param1=1, param2=1)
                await mission_handler.wait_for_mission_completion()

            lap_start = time.perf_counter()
            log_system(msgname="CTT", msg=f"Lap {lap} started")

            # Wait for mission to complete this lap
            await mission_handler.wait_for_mission_completion()

            lap_time = time.perf_counter() - lap_start
            self.lap_times.append(lap_time)
            total_time += lap_time

            if lap_time < best_time:
                best_time = lap_time

            log_success(msgname="CTT",
                        msg=f"Lap {lap} complete — {lap_time:.2f}s | Best so far: {best_time:.2f}s")

        log_success(msgname="Soaring Skies",
                    msg=f"Time Trial complete. Best lap: {best_time:.2f}s | Total: {total_time:.2f}s")

    # ------------------------------------------------------------------
    # TASK B: AIRDROP
    # ------------------------------------------------------------------

    async def _run_airdrop(self):
        log_system(msgname="Soaring Skies",
                   msg="--- Starting Task B: Target ID & Airdrop ---",
                   color=bcolors.OKCYAN)

        if not self.searchBoundaryFile:
            log_fail(msgname="Soaring Skies",
                     msg="No search boundary file provided. Skipping airdrop task.")
            return

        # Remaining timeout for the imaging system
        remaining = self._time_remaining()
        imaging_timeout = max(30.0, remaining - self.TIMEOUT_BUFFER)
        self.target_loc.imaging_timeout = imaging_timeout

        await self.target_loc.run(
            waypointsFile=self.searchBoundaryFile,
            rtl=False   # SoaringSkiesMission handles RTL at the top level
        )
        self.airdrop_success = self.target_loc.airdrop.dropped

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _time_remaining(self) -> float:
        if self._flight_start is None:
            return self.FLIGHT_TIME_LIMIT
        elapsed = time.perf_counter() - self._flight_start
        return max(0.0, self.FLIGHT_TIME_LIMIT - elapsed)

    def _print_summary(self):
        elapsed = time.perf_counter() - self._flight_start if self._flight_start else 0
        log_system(msgname="Soaring Skies", msg="=== FLIGHT SUMMARY ===", color=bcolors.HEADER)
        log_system(msgname="Soaring Skies", msg=f"Total flight time: {elapsed:.1f}s / {self.FLIGHT_TIME_LIMIT}s")

        if self.lap_times:
            best = min(self.lap_times)
            for i, t in enumerate(self.lap_times, 1):
                log_system(msgname="CTT", msg=f"  Lap {i}: {t:.2f}s")
            log_success(msgname="CTT", msg=f"  Best lap: {best:.2f}s")
        else:
            log_fail(msgname="CTT", msg="  No lap times recorded.")

        if self.airdrop_success:
            log_success(msgname="Airdrop", msg="  Payload dropped successfully.")
        else:
            log_fail(msgname="Airdrop", msg="  Payload was NOT dropped.")
