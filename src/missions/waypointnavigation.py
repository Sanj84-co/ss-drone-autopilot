import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

from utils.drone import Drone, DroneProperties
from utils.mission import Mission

from utils.logger import log_success, log_system, log_fail
from utils.takeoff import takeoff,return_to_launch
import utils.mode as mode
from helper.file_reader import read_waypoints
from helper.math_funcs import haversine_distance

import time

class   WaypointNavigation:
    def __init__(self, drone: Drone, waypointsFile = None):
        self.drone = drone
        self.custom_points = None
        self.mission_handler = Mission(drone=drone)
        self.waypointsFile = waypointsFile
        pass

    async def get_sorted_waypoints(self, waypoints: list = None):

        current_pos = await self.drone.get_home_position_deg()
        current_pos = [current_pos['lat'],current_pos['long'],current_pos['alt']]
        sorted_points = []
        size = len(waypoints)
        for i in range(size):
            next_point = None
            distance = 1e11
            for point in waypoints:
                if haversine_distance(point, current_pos) < distance:
                    distance = haversine_distance(point, current_pos)
                    next_point = point
            sorted_points.append(next_point)
            waypoints.remove(next_point)
            current_pos = next_point


        return sorted_points

    async def upload_mission(self, waypointsFile = None, rtl = True):
        waypoints = read_waypoints(waypointsFile) if waypointsFile else read_waypoints(self.waypointsFile)
        if self.custom_points is not None:
            waypoints = self.custom_points
        waypoints = await self.get_sorted_waypoints(waypoints)
        await self.mission_handler.upload_mission(waypoints=waypoints, rtl=rtl)
        await self.mission_handler.begin_mission()
        
        
    async def test_point_sorting(self, waypointsFile = None):
        waypoints = read_waypoints(waypointsFile) if waypointsFile else read_waypoints(self.waypointsFile)
        
        print(f'UNSORTED POINTS: {waypoints}')
        sorted_points = await self.get_sorted_waypoints(waypoints)
        print(f'\nSORTED POINTS: {sorted_points}')
        

    


