import time
import serial

ser = serial.Serial(
    port="COM3",
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1.0,
    write_timeout=1.0,
)

time.sleep(0.5)

# Discard any old bytes
ser.reset_input_buffer()
ser.reset_output_buffer()

commands = [
    b"*IDN?\r",       # Newer Cobolt protocol
    b"gfv?\r",        # Legacy firmware-version command
    b"gsn?\r",        # Legacy serial-number command
]

for command in commands:
    ser.reset_input_buffer()
    print("Sending:", repr(command))

    ser.write(command)
    ser.flush()

    time.sleep(0.2)
    response = ser.read_until(b"\r")

    print("Received:", repr(response))

ser.close()