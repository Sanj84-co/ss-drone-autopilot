from pymavlink import mavutil
from pymavlink.dialects.v20 import common
import asyncio

class bcolors:
    # https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797
    HEADER = '\033[95m'
    COMMAND = '\033[94m' # darkish blue
    OKCYAN = '\033[96m' # guess
    OKGREEN = '\033[92m' # guess
    YELLOW = '\033[93m' # guess
    FAIL = '\033[91m' # bright red
    HEARTBEAT = '\033[31m' # red
    ENDC = '\033[0m' # stops the formatting
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    MISSION = '\033[38;5;157m' # for messages starting with MISSION_* (light greenish)
    SUCCESS = '\033[38;5;82m' # green 


async def logger(stream:asyncio.Queue): 
    '''DEPRECATED - Functionality of this function integrated into handle_message() in messages.py'''
    while True:
        msg = await stream.get()
        # print('getting from message-stream')
        log_message(msg)

def log_message(msg):
    '''Used to log MAVLINK messages ONLY. DO NOT USE FOR CUSTOM MESSAGES'''
    if msg.msgname == 'HEARTBEAT' and msg.type == 2:
        print(f'{bcolors.HEARTBEAT + 'Drone -> GCS' + bcolors.ENDC} {msg}')
        return
    elif msg.msgname == 'HEARTBEAT' and msg.type == 6:
        # print(f'{bcolors.HEARTBEAT + msg.msgname + ' (gcs)  > ' + bcolors.ENDC} {msg}')
        return
    elif msg.msgname == 'COMMAND_ACK':
        command_log(msg)
    elif msg.msgname.__contains__('MISSION'):
        mission_log(msg)
    else:
        print(f'{bcolors.YELLOW + msg.msgname + bcolors.ENDC} > {msg}')

def log_custom(msg, important = False):
    '''Legacy function, recommended to use log_system instead
        \nLogs a custom message (shows up as yellow), but if the important parameter is set to True, message color is red.'''
    print(f'{(bcolors.FAIL + '[IMPORTANT] ') if important else bcolors.YELLOW}{bcolors.UNDERLINE}CUSTOM{bcolors.ENDC} > {msg}')

def log_system(msg, msgname = 'SYSTEM', color = bcolors.YELLOW):
    '''Preferred function for logging. Can be used to customize the message name, message and color of message using the bcolors class'''
    print(f'{color}{bcolors.BOLD}{msgname}{bcolors.ENDC} > {msg}')

def command_log(msg):
    '''For logging commands and the command result. command_result integer is GREEN if accepted, RED if denied or YELLOW if other'''
    print_str = (f'{bcolors.COMMAND + msg.msgname + bcolors.ENDC} ({bcolors.OKCYAN}{msg.command}{bcolors.ENDC}) - ')
    match msg.result:
        case common.MAV_RESULT_ACCEPTED:
            print_str = print_str + f'{bcolors.OKGREEN}{'ACCEPTED'}{bcolors.ENDC}'
            pass
        case common.MAV_RESULT_DENIED:
            print_str = print_str + f'{bcolors.FAIL}{'DENIED'}{bcolors.ENDC}'
            pass
        case _:
            print_str = print_str + f'{bcolors.YELLOW}{msg.result }{bcolors.ENDC}'
    
    print_str = print_str + f' > {msg}'
    print(print_str)

def mission_log(msg):
    '''Used to log a mission_ack message and is clear if the mission has been uploaded or not'''
    if msg.msgname == 'MISSION_ACK':
        print(f'{bcolors.MISSION}{msg.msgname}{bcolors.ENDC} - {(bcolors.OKGREEN + 'UPLOADED') if msg.type == 0 else (bcolors.FAIL + 'NOT UPLOADED')}{bcolors.ENDC} > {msg}')
    else:
        print(f'{bcolors.MISSION}{msg.msgname}{bcolors.ENDC} > {msg}')

def log_success(msg, msgname="SUCCESS"):
    '''Used to log a successful action'''
    log_system(msg=msg, msgname=msgname, color=bcolors.SUCCESS)

def log_fail(msg, msgname="FAILED"):
    '''Used to log a failed action'''
    log_system(msg=msg, msgname=msgname, color=bcolors.FAIL)
