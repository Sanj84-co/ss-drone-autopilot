import asyncio
from pymavlink import mavutil
from pymavlink.dialects.v20 import common
from utils.logger import log_custom, log_message, log_system, bcolors, logger
import helper.file_reader as reader 

class MessageStream:

    
    def __init__(self, connection: mavutil.mavfile):
        self.important_messages = None
        self.stored_messages: dict[str, asyncio.Future] = {}
        self.connection = connection
        log_system(msg="Initializing Message Stream")
        self.stream = asyncio.Queue()
        self.listening = False
        # asyncio.create_task(self.message_stream())
        
        pass

    def initialize_important_messages(self, file = 'info_files/important_messages.txt'):
        '''Stores all important messages to a list. When a message is recieved it is compared to the elements of the array, and if the message names match,
        then the message is stored '''
        if not self.connection is None:
            self.important_messages = reader.file_to_list(file)
            print(f'initialized all important messages :) --> {self.important_messages}')

    async def message_stream(self):
        '''A function that runs infinitely that listens for messages from the drone'''
        self.initialize_important_messages()
        self.listening = True
        while True:
            msg = self.connection.recv_match(blocking=False) 
            if msg:
                log_message(msg)
                try:
                    asyncio.create_task(self.handle_message(msg))
                except TimeoutError:
                    pass
            await asyncio.sleep(0.1)

    async def request_message(self, message_id: int):
        '''Used to request a specific messages'''
        await self.send_command(command= common.MAV_CMD_REQUEST_MESSAGE, param1= message_id)
        target_message = common.mavlink_map.get(message_id).msgname
        print(f'waiting for message {target_message}')
        if(target_message == "COMMAND_ACK" or target_message == 'MISSION_ACK'):
            return await self.wait_for_message(target_message, secondary=f'{message_id}')
        return await self.wait_for_message(target_message)

            
    async def send_command(self, command, 
                           param1 = 0, param2 = 0, param3 = 0, param4 = 0, param5 = 0, param6 = 0, param7 = 0, timeout = 3):
        '''Sends a command using command_long. NOT RECOMMENDED for commands that deal with integer coordinates \n\nUse send_command_int() instead'''
        self.connection.mav.command_long_send(self.connection.target_system, self.connection.target_component, command, 0, 
                                         param1,param2,param3,param4,param5,param6,param7)
        # print(f"SENT COMMAND {command}")
        # ack =  await self.wait_for_message(f'COMMAND_ACK.{command}')
        try:
            ack = await asyncio.wait_for(self.wait_for_message(f'COMMAND_ACK', secondary=command), timeout=timeout)
            # log_custom(f'recieved command ack code: {command}')
        except TimeoutError:
            log_system(color=bcolors.FAIL, msg=f"FAILED TO RECIEVE COMMAND_ACK ({command})")
            await self.send_command(command,param1,param2,param3,param4,param5,param6,param7)
            return

        if(ack.result != 0):
            log_system(msg = "PASSING INTO RESULT HANDLER...STANDBY", msgname="ACK_HANDLER")
            await self.result_handler(ack, command, param1, param2, param3, param4,param5,param6,param7)
        return ack # no harm in return the command_ack
        
    async def send_command_int(self, command, 
                           param1 = 0, param2 = 0, param3 = 0, param4 = 0, x = 0, y = 0, z = 0, timeout = 5, frame=common.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT):
        '''Sends a command using command_int_send. Recommended for when sending commands that require integer positions as parameters. Also recommended that you specify each parameter passed in'''
        self.connection.mav.command_int_send(self.connection.target_system, self.connection.target_component, frame, command, 0, 0, 
                                         param1,param2,param3,param4,x,y,z)
        # print(f"SENT COMMAND {command}")
        # ack =  await self.wait_for_message(f'COMMAND_ACK.{command}')
        try:
            ack = await asyncio.wait_for(self.wait_for_message(f'COMMAND_ACK', secondary=command), timeout=timeout)
            log_custom(f'recieved command ack code: {command}')
        except TimeoutError:
            log_system(color=bcolors.FAIL, msg=f"FAILED TO RECIEVE COMMAND_ACK ({command})")
            return

        if(ack.result != 0):
            log_system(msg = "PASSING INTO RESULT HANDLER...STANDBY", msgname="ACK_HANDLER")
            await self.result_handler(ack, command, param1, param2, param3, param4,x,y,z, frame=frame)
        return ack # no harm in return the command_ack

    
    async def result_handler(self, ack, command, 
                           param1 = 0, param2 = 0, param3 = 0, param4 = 0, param5 = 0, param6 = 0, param7 = 0, retries: int =3, frame=False):
        match ack.result:
            case 1: # MAV_RESULT_TEMPORARILY_REJECTED
                log_system(msg = "MAV RESULT TEMP REJECTED. RETRYING COMMAND IN 1 SECOND", msgname="ACK_HANDLER (RETRYING)")
                await asyncio.sleep(1)
                if(retries > 1):
                    if frame is False:
                        await self.send_command(command, 
                                   param1, param2, param3, param4, param5, param6, param7, retries=retries-1)
                    else:
                        await self.send_command_int(command, 
                                   param1, param2, param3, param4, param5, param6, param7, retries=retries-1, frame=frame)
                else:
                    log_system(msg='COMMAND REJECTED TOO MANY TIMES', color=bcolors.FAIL)
            case 2: # MAV_RESULT_DENIED
                log_system(msgname="ACK_HANDLER (ERROR)", color=bcolors.FAIL, msg="MAV RESULT FAILED. ONE OR MORE PARAMETERS INVALID")
            case 3: # MAV_RESULT_UNSUPPORTED
                log_system(msg="COMMAND UNSUPPORTED", msgname="ACK_HANDLER (UNSUPPORTED)")
            case 4: #MAV_RESULT_FAILED
                log_system(msgname="ACK_HANDLER (FAILED)", msg="COMMAND FAILED TO EXECUTE. UNEXPECTED PROBLEM OCCURED")
        pass

    # This class given msg or an array of messages, can wait for a specific message to arrive. It creates an asyncio future, and adds it to the
    # stored_messages dictionary, and once the result of the future is set by the message handler in handle_message(), it returns the message
    async def wait_for_message(self, *msgs, secondary = None):  
        for msg in msgs:
            future = asyncio.get_running_loop().create_future()
            # print(f'msg = {msg}')
            # if self.important_messages.__contains__(msg):
                # print(f'Added {msg.msgname} to important message dict')
            if msg == 'COMMAND_ACK':
                # print(f'adding future {msg}.{secondary}')
                self.stored_messages[f'{msg}.{secondary}'] = future
            elif msg == 'MISSION_ACK' or msg == 'MISSION_REQUEST' or msg == 'MISSION_REQUEST_INT':
                self.stored_messages[f'{msg}.{secondary}'] = future
            # elif secondary is not None:
            #     self.stored_messages[f'{msg}.{secondary}'] = future
            else:
                self.stored_messages[f'{msg}'] = future

            await future
            return future.result()
            # if(self.stored_messages.__contains__(msg)):
                #     ack = self.stored_messages.pop(msg)
                #     # print(f'Recieved {msg}') # REMOVE THIS LATER
                #     return ack
            # print(f'Waiting for {msg}') # REMOVE THIS LATER
            # await asyncio.sleep(0.2)

    async def handle_message(self, msg):
        # await self.stream.put(msg)

        if self.important_messages.__contains__(msg.msgname):
            if msg.msgname == 'COMMAND_ACK':
                try:
                    # print('setting result')
                    if self.stored_messages.keys().__contains__(f'{msg.msgname}.{msg.command}'):
                        if not self.stored_messages[f'{msg.msgname}.{msg.command}'].done():
                            self.stored_messages[f'{msg.msgname}.{msg.command}'].set_result(msg)
                    else:
                        await asyncio.sleep(1)
                        await self.handle_message(msg=msg)
                except KeyError:
                    print("Key Error")
                    pass
            elif msg.msgname == 'MISSION_ACK'or msg.msgname == 'MISSION_REQUEST' or msg.msgname == 'MISSION_REQUEST_INT':
                try:
                    if self.stored_messages.keys().__contains__(f'{msg.msgname}.{msg.mission_type}'):
                        # print(f'GLOOB {self.stored_messages[f'{msg.msgname}.{msg.mission_type}']}')
                        if not self.stored_messages[f'{msg.msgname}.{msg.mission_type}'].done():
                            self.stored_messages[f'{msg.msgname}.{msg.mission_type}'].set_result(msg)
                    else:
                        await asyncio.sleep(1)
                        await self.handle_message(msg=msg)
                except KeyError:
                    print("Key Error")
                    pass
            else:
                # print(f'Stored {msg.msgname}')
                try:
                    if self.stored_messages.keys().__contains__(f'{msg.msgname}'):
                        if not self.stored_messages[f'{msg.msgname}'].done():
                            self.stored_messages[f'{msg.msgname}'].set_result(msg)
                    else:
                        await asyncio.sleep(1)
                        await self.handle_message(msg=msg)
                except KeyError:
                    print("Key Error")
                    pass
                

    
        
    