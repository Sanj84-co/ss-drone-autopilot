import asyncio
from utils.drone import Drone
from pymavlink.dialects.v20 import common
from pymavlink import mavutil

# USE mavutil.mode_mapping_rover for mode numbers

STABILIZE = 0
AUTO = 3
GUIDED = 4
LOITER = 5
RTL = 6

async def set_mode(drone: Drone, mode: int):
    # mode_map = {'stabilize': 0, 'auto': 3, 'guided': 4, 'loiter': 5, 'rtl': 6}
    print(f'Setting mode to {mode}')

    await drone.send_command(command=common.MAV_CMD_DO_SET_MODE, param1=common.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, param2=mode)
    await asyncio.sleep(0.5) # waiting for 0.5 seconds to allow for drone to finish switching modes
    

