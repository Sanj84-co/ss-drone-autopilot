import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

from utils.drone import Drone
from utils.logger import log_system, log_fail
import utils.mode as mode
from utils.armdisarm import arm_drone, disarm_drone
from utils.takeoff import takeoff, return_to_launch, wait_for_altitude_decrease, wait_for_altitude_increase

async def reposition_drone_deg(drone: Drone, coordinates: list = None):
    await drone.message_stream_exists()

    if not coordinates:
        log_fail(msg="Reposition Failed! No coordinates provided", msgname="REPOSITION")
        return
    
    lat = coordinates[0]
    long = coordinates[1]
    alt = coordinates[2]
    print(f'target alt of {alt}')
    if not alt:
        alt = drone.target_alt
    
    await arm_drone(drone=drone)
    await mode.set_mode(drone, mode.GUIDED)
    
    await takeoff(drone=drone, target_alt=alt)
    

    # print('sending pos target globa int')
    drone.get_connection().mav.set_position_target_global_int_send(
        0,                                          # time boot (ms)
        drone.get_connection().target_system,       # target system
        drone.get_connection().target_component,    # target component
        common.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,   # frame
        0b111111111000,                            # position target typemask
        (int)(lat * 1e7),                                # latitude * 10^6
        (int)(long * 1e7),                               # longitude * 10^6
        alt,                                        # relative altitude (meters)
        0,0,0,0,0,0,0,0
    )
    # print('SENT pos target globa int')
    pos_target = await drone.get_message_stream().request_message(common.MAVLINK_MSG_ID_POSITION_TARGET_GLOBAL_INT)
    # print('recieved pos target global int')
    print(pos_target.lat_int)
    print(pos_target.lon_int)
    print(pos_target.alt)

async def change_altitude(drone: Drone, alt_change):
    '''Allows drone to increase/decrease altitude in whatever units is described'''
    current_pos = await drone.get_position_deg()

    await reposition_drone_deg(drone=drone, coordinates=[current_pos['lat'], current_pos['long'], current_pos['alt']+alt_change])

    if alt_change > 0:
        await wait_for_altitude_increase(drone, current_pos['alt']+alt_change)
    else:
        await wait_for_altitude_decrease(drone, current_pos['alt']+alt_change)
    