import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

from utils.drone import Drone, DroneProperties
import utils.mode as mode
from utils.mission import Mission
from utils.armdisarm import arm_drone
from utils.logger import log_system
from utils.takeoff import return_to_launch

from helper.file_reader import read_waypoints
import time
class CircuitTimeTrial:
    def __init__(self, drone: Drone, waypointsFile: str = None):
        self.drone = drone
        self.custom_points = read_waypoints(waypointsFile) if waypointsFile else None
        self.mission_handler = Mission(drone=drone, waypointsFile=waypointsFile)
        pass

    async def upload_mission(self, waypointsFile = None, rtl: bool = True):
        waypoints = read_waypoints(waypointsFile) if waypointsFile else None
        if self.custom_points is not None:
            waypoints = self.custom_points

        home_pos = await self.drone.get_home_position_deg()
        waypoints.append([home_pos['lat'], home_pos['long'], home_pos['alt']])
        print(f'WAYPOINTS == {waypoints}')
        lap = 1
        total_time_elapsed = 0
        while True:
            if lap > 3:
                break
            if lap == 1:
                await self.mission_handler.upload_mission(waypoints=waypoints, begin_immediately=False)
                lap_start = time.perf_counter()
                log_system(msgname="CTT Timekeeper", msg=f'Beginning Lap {lap}')
                await self.mission_handler.begin_mission(rtl=False)
            else:
                await self.drone.send_command(command=common.MAV_CMD_DO_SET_MISSION_CURRENT, param1=1, param2=1)
                log_system(msgname="CTT Timekeeper", msg=f'Beginning Lap {lap}')

            lap_end = time.perf_counter()
            log_system(msgname="CTT Timekeeper", msg=f'Time to finish lap {lap}: {lap_end-lap_start} seconds')
            total_time_elapsed = total_time_elapsed + (lap_end - lap_start)
            lap = lap + 1
        
        log_system(msgname="CTT Timekeeper", msg=f"All laps exhausted. Total time elapsed: {total_time_elapsed} seconds")
        if rtl:
            await return_to_launch(self.drone)