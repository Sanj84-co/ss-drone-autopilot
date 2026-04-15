import asyncio
from pymavlink.dialects.v20 import common

from utils.drone import Drone
from utils.armdisarm import arm_drone
from utils.logger import log_system, bcolors

async def test_all_motors(drone: Drone, throttle_value: int = 10):
    
    log_system(msgname="MOTOR TEST INITIATING", msg="Motor test beginning in 3 seconds. Make sure all props have been removed. " \
    "Kill this program if not.", color=f'{bcolors.BOLD}{bcolors.UNDERLINE}{bcolors.OKCYAN}')

    await asyncio.sleep(3)

    log_system(msg="BEGINNING MOTOR TEST", msgname="MOTOR TEST INITIATING", color=f'{bcolors.BOLD}{bcolors.UNDERLINE}{bcolors.OKCYAN}')

    await arm_drone(drone=drone)
    
    motor1, motor2, motor3, motor4 = [1,2,3,4]
    throttle_type = common.MOTOR_TEST_THROTTLE_PERCENT
    timeout = 1
    motor_count = 4
    test_order = common.MOTOR_TEST_ORDER_DEFAULT
    await drone.send_command(command=common.MAV_CMD_DO_MOTOR_TEST, 
                             param1=motor1, 
                             param2=throttle_type, 
                             param3=throttle_value,
                             param4=timeout,
                             param5=motor_count,
                             param6=test_order,
                             param7=0)
    await asyncio.sleep(timeout*motor_count+1)
    
async def test_all_motors_multiple(drone: Drone, num_times: int = 1, throttle_value:int = 5, throttle_step: int = 0):
    for i in range(num_times):
        log_system(msg=f"Testing Motors | Iteration {i+1} | Throttle Value {throttle_value+i*throttle_step}%")
        await test_all_motors(drone=drone, throttle_value=(throttle_value+i*throttle_step))