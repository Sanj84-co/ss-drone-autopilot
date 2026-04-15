import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

from utils.drone import Drone, DroneProperties
from utils.logger import log_system,log_success, log_fail


async def change_speed(drone: Drone, speed: int = -1, throttle: int = -1):
    '''used to change the speed of a given drone, to an input speed (in meters/second). Throttle can also be specified'''
    if speed == -1:
        speed = drone.groundspeed
    speed_ack = await drone.send_command(command=common.MAV_CMD_DO_CHANGE_SPEED, param1=common.SPEED_TYPE_GROUNDSPEED, param2=speed, param3=throttle)
    log_system(msgname=DroneProperties.SPEED_HANDLER, msg=f"Do change speed command sent. Attempting to change speed to {speed} and throttle to {throttle}")
    