# base imports
import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common

# util imports
from utils.messages import MessageStream
from utils.logger import bcolors, log_system

# etc imports
from helper.file_reader import read_config_file

class Drone:
    def __init__(self):
        self.message_stream = None
        print('initializing drone')
        self.home_position = {
            'lat': -1, 'long':-1, 'alt': -1, 'set': False}


    def retrieve_configuration(self, parametersFile = None, configFile = None):
        '''Reads the drone settings file and initializes parameters to Drone instance'''
        params = read_config_file(parametersFile) if parametersFile else -1
        print(params)
        self.target_alt = int(params['altitude']) if parametersFile else 10
        self.threshhold = float(params['threshhold']) if parametersFile else 0.2
        self.threshholdZ = float(params['threshholdZ']) if parametersFile else 0.1
        self.climbspeed = int(params['climbspeed']) if parametersFile else -1
        self.groundspeed = int(params['groundspeed']) if parametersFile else -1
        self.airspeed = int(params['airspeed']) if parametersFile else -1
        self.servo_num = int(params['servo_num']) if parametersFile else -1
        self.square_size = int(params['square_size']) if parametersFile else 1
        self.meters = True if (parametersFile and int(params['meters']) == 0) else False
        self.camera_url = params["camera_url"] if parametersFile else None

        if(configFile):
            self.config = read_config_file(configFile)
            print(self.config)

    def connect_drone(self,connection_string = 'tcp:127.0.0.1:5763', port = False):
        '''This method is used to connect to the drone given the connection string'''
        print(connection_string)
        self.connection: mavutil.mavtcp = mavutil.mavlink_connection(device=connection_string) # specifying baud rate breaks everything
        self.connection.wait_heartbeat()
        log_system(msg=f"{bcolors.HEADER} -- Connected to {connection_string} on port {port if port else "NO PORT"} with system id {self.connection.target_system} and component id {self.connection.target_component} --{bcolors.ENDC}", color=bcolors.SUCCESS)
        self.message_stream = MessageStream(self.connection)
        # while True:
        #     print(self.connection.recv_match(blocking=True))
        
    def initialize_drone(self, parametersFile, configFile):
        self.retrieve_configuration(parametersFile,configFile)
        self.connection_str: str = self.config[DroneProperties.CONNECTION]
        try:
            if(self.connection_str.__contains__(':')):
                self.port = self.connection_str[self.connection_str.index(':')]
            else:
                self.port = False
        except Exception: 
            print('exception idk in intialize_drone() in drone.py')
        
        self.connect_drone(connection_string=self.connection_str, port=self.port)


    async def send_heartbeat(self):
        while True:
            self.get_connection().mav.heartbeat_send(common.MAV_TYPE_GCS, common.MAV_AUTOPILOT_INVALID, 0,0,0)
            log_system(msgname=f"{DroneProperties.HEARTBEAT_SEND}", msg="Sent heartbeat to drone from GCS", color=bcolors.HEARTBEAT)
            await asyncio.sleep(1)

    async def send_command(self, command: int, param1 = 0, param2 = 0, param3 = 0, param4 = 0, param5 = 0, param6 = 0, param7 = 0, timeout = 5):
        '''Sends a command using command_long. NOT RECOMMENDED for commands that deal with integer coordinates \n\nUse send_command_int() instead'''
        print(f"SENDING COMMAND LONG {command}")
        return await self.message_stream.send_command(command=command, param1=param1, param2=param2, param3=param3, param4=param4,
                                                                          param5=param5, param6=param6, param7=param7, timeout=timeout)
    
    async def send_command_int(self, command: int, param1 = 0, param2 = 0, param3 = 0, param4 = 0, param5 = 0, param6 = 0, param7 = 0, timeout = 5, frame=common.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT):
        '''Sends a command using command_int_send. Recommended for when sending commands that require integer positions as parameters. Also recommended that you specify each parameter passed in'''
        print(f"SENDING COMMAND INT {command}")
        return await self.message_stream.send_command_int(command=command, param1=param1, param2=param2, param3=param3, param4=param4,
                                                                          param5=param5, param6=param6, param7=param7, timeout=timeout, frame=frame)

    async def message_stream_exists(self, msg = None, msgname = None):
        while True:
            if (self.message_stream and self.message_stream.listening):
                return
            if(msg and msgname):
                log_system(msgname=msgname, msg=msg)    
            await asyncio.sleep(0.5)

    # TO DO: Create failsafe + activate failsafe
    async def watch_for_heartbeat(self):
        '''This async function watches for the drones heartbeat and keep track of if more than five consecutive heartbeats have been missed.
        Once five consecutive heartbeats have been missed, the emergency failsafe should activate'''
        await self.message_stream_exists(msgname='Heartbeat Watcher', msg="Message Stream not yet initialized | Awaiting Message Stream activation")
        retries = 5
        while True:
            if retries == 0:
                log_system(msg="Drone connection lost...", msgname="Heartbeat Watcher (CRITICAL FAILURE)", color=bcolors.FAIL)
                break
            try:
                hb = await asyncio.wait_for(self.message_stream.wait_for_message("HEARTBEAT"), timeout=1.1)
                # print('heartbeat recieved from drone')
                retries = 5
            except TimeoutError:
                log_system(msgname="Heartbeat Watcher (URGENT)", msg=f"Too long since last heartbeat recieved. {retries-1} retries until failsafe activation", color=bcolors.HEARTBEAT)
                retries -= 1
        i = 1
        while True:
            log_system(msg=f"Heartbeats missed: {i}", msgname="Heartbeat Watcher (CRITICAL FAILURE)", color=bcolors.FAIL)
            i += 1
            await asyncio.sleep(1)

    async def start_background_processes(self):
        # asyncio.new_event_loop()
        asyncio.create_task(self.message_stream.message_stream())
        asyncio.create_task(self.set_home_position())
        asyncio.create_task(self.send_heartbeat())
        
    def unit_corrector(self, value):
        if self.meters: 
            return value
        else:
            return value * 3.281
        
    # GETTERS
    def get_configuration(self):
        return self.config
    def get_connection(self):
        return self.connection
    def get_message_stream(self):
        return self.message_stream
    
    async def set_home_position(self):
        await self.message_stream_exists(msgname="Home Position", msg="Message Stream not yet initialized | Awaiting Message Stream activation")
        log_system(msgname="Home Position", msg="Requesting Home Position")
        pos_msg = await self.get_message_stream().request_message(common.MAVLINK_MSG_ID_GLOBAL_POSITION_INT)
        home_pos = {'lat': pos_msg.lat, 'long':pos_msg.lon, 'alt': (pos_msg.relative_alt/1000), 'set': True}
        self.home_position = home_pos
        log_system(msgname="Home Position", msg="Home Position Set Successfully", color=bcolors.SUCCESS)

    async def get_home_position_int(self):
        while True:
            if(self.home_position['set']):
                return self.home_position 
            await asyncio.sleep(0.5)

    async def get_home_position_deg(self):
        home_pos = await self.get_home_position_int()
        home_pos['lat'] = home_pos['lat']/1e7
        home_pos['long'] = home_pos['long']/1e7
        return home_pos

    async def get_position_deg(self):
        current_pos = await self.get_message_stream().request_message(common.MAVLINK_MSG_ID_GLOBAL_POSITION_INT)
        return {"lat": current_pos.lat, "long": current_pos.lon, "alt": (self.unit_corrector(current_pos.relative_alt/1000))}



class DroneProperties:

    CONNECTION = 'connection'
    BAUD = 'baud'
    MISSION = 'mission'
    MISSION_HANDLER = 'Mission Handler'
    HEARTBEAT_SEND = 'GCS -> Drone'
    HEARTBEAT_RECIEVE = 'Drone -> GCS'
    SPEED_HANDLER = "Speed Handler"
    
    
