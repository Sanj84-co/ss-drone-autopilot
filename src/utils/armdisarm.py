import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

from utils.drone import Drone, DroneProperties

async def arm_drone(drone:Drone, force=False):
    await drone.send_command(command=common.MAV_CMD_COMPONENT_ARM_DISARM, param1=common.MAV_BOOL_TRUE, param2=(21196 if force else 0))

async def disarm_drone(drone:Drone, force: bool = False):
    await drone.send_command(command=common.MAV_CMD_COMPONENT_ARM_DISARM, param1=common.MAV_BOOL_FALSE, param2=(21196 if force else 0))
    