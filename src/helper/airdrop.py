import asyncio
from pymavlink.dialects.v20 import common
from utils.drone import Drone
from utils.logger import log_system, log_success, log_fail, bcolors

# PWM values for servo positions
SERVO_OPEN_PWM  = 2000   # PWM to open the airdrop mechanism (release payload)
SERVO_CLOSED_PWM = 1000  # PWM to close/reset the airdrop mechanism

class Airdrop:
    def __init__(self, drone: Drone, servo_num: int = None):
        '''
        servo_num: The servo channel number (1-8 for MAIN, 9-16 for AUX).
                   Defaults to the servo_num from drone settings.
        '''
        self.drone = drone
        self.servo_num = servo_num if servo_num is not None else drone.servo_num
        self.dropped = False

    async def arm_airdrop(self):
        '''Closes/resets the servo to the armed (holding) position.'''
        log_system(msgname="Airdrop", msg=f"Arming airdrop mechanism on servo {self.servo_num}...")
        await self._set_servo(SERVO_CLOSED_PWM)
        log_success(msgname="Airdrop", msg="Airdrop mechanism armed (closed).")

    async def release(self):
        '''Opens the servo to release the payload. Resets after 1 second.'''
        if self.dropped:
            log_fail(msgname="Airdrop", msg="Airdrop already triggered. Cannot drop again.")
            return False

        log_system(msgname="Airdrop", msg=f"RELEASING PAYLOAD on servo {self.servo_num}!", color=bcolors.FAIL)
        await self._set_servo(SERVO_OPEN_PWM)
        await asyncio.sleep(1.0)  # hold open for 1 second to ensure release
        await self._set_servo(SERVO_CLOSED_PWM)  # reset servo
        self.dropped = True
        log_success(msgname="Airdrop", msg="Payload released successfully.")
        return True

    async def _set_servo(self, pwm_value: int):
        '''Sends the MAVLink command to set the servo to a given PWM value.'''
        await self.drone.send_command(
            command=common.MAV_CMD_DO_SET_SERVO,
            param1=self.servo_num,
            param2=pwm_value
        )

    def reset(self):
        '''Resets the dropped flag (use only if retrying).'''
        self.dropped = False
        log_system(msgname="Airdrop", msg="Airdrop state reset.", color=bcolors.YELLOW)
