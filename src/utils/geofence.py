import asyncio
from pymavlink import mavutil 
from pymavlink.dialects.v20 import common

from helper.file_reader import read_geofence
from utils.drone import Drone, DroneProperties
from utils.logger import log_custom


class Geofence:
    def __init__(self, drone: Drone, geofenceFile='info_files/fence.txt'):
        self.drone = drone
        self.fence = read_geofence(geofenceFile)

    async def configure_fence(self):
        await self.drone.send_command(common.MAV_CMD_DO_FENCE_ENABLE, param1=1)
        self.drone.get_connection().mav.mission_clear_all_send(
            self.drone.get_connection().target_system,
            self.drone.get_connection().target_component,
            common.MAV_MISSION_TYPE_FENCE
        )
        log_custom('Fence Cleared')

    async def fence_setup(self):
        await self.configure_fence()
        clean_points = []
        for gf in self.fence:
            if gf[0] < 1e5 and gf[1] < 1e5:
                clean_points.append([
                    (int)(gf[0]*1e7), # lat
                    (int)(gf[1]*1e7) # long
                    # gf[2] # altitude, for some reason they gave altitude
                    ])
            else:
                clean_points.append(gf)
        return clean_points

    async def upload_fence(self):
        points = await self.fence_setup()
        connection = self.drone.get_connection()
        connection.mav.mission_count_send(connection.target_system, connection.target_component, len(points),
                                          common.MAV_MISSION_TYPE_FENCE, 0)
        log_custom(f'Sending fence length of {len(points)} | Waiting for mission request')
        print(points)
        for i, point in enumerate(points, start=0):
            await self.drone.get_message_stream().wait_for_message('MISSION_REQUEST', 'MISSION_REQUEST_INT', secondary=common.MAV_MISSION_TYPE_FENCE)
            connection.mav.mission_item_int_send(connection.target_system, connection.target_component, i,
                                                 common.MAV_FRAME_GLOBAL_INT,
                                                 common.MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION,
                                                 0, 1, len(points), 0, 0, 0, point[0], point[1], 0,
                                                 common.MAV_MISSION_TYPE_FENCE)
            log_custom(f'Sending Fence Item {i}', important=True)