import asyncio
from pymavlink.dialects.v20 import common
from pymavlink import mavutil

from utils.drone import Drone

# FOR servo_num, 1-8 is for the MAIN channels 1-8 and 9-16 is for AUX channels
# we'll use MAIN channels since the AUX channels are used for ESCs

async def test_servo(drone: Drone, servo_num: int = 0, servo_value: int = 1000):
    ack = await drone.send_command(command=common.MAV_CMD_DO_SET_SERVO, param1=servo_num, param2=servo_value)
    await asyncio.sleep(2)
    pass

async def full_spin_servo(drone, servo_num):
    await test_servo(drone, servo_num, 2500)
    await test_servo(drone, servo_num, 500)