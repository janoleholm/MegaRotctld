# Object version of K3NGRotctld.py
import socket
import threading
import asyncio
import serial
import time
from datetime import datetime
from coor_table import Correction_table

# Opret en socket og lyt på port 4575
host = 'localhost'
port = 4575

# Command strings
# Query azimuth and elevation in K3NG Full Status command:
# \?FS                                                                                                                            
# \!OKFS215.163380,+047.042171,0,0,+55.0681,+010.6171,1,2024-10-21 10:19:48Z;                                                     

# Gloabal variables contains what rotor sensors reports WITHOUT correction
az_raw_global = 180.0
el_raw_global = 30.0
# Gloabal variables WITH correction to Get-values
az_rotor_global = 0.0
el_rotor_global = 0.0
# Global variables contains floats of what SDRangel request rotor to move to
az_set_global = 180.0
el_set_global = 30.0
# AZ / EL correction constant - Don't make them zero 0.0!!
az_coor = -0.3   #1.73
el_coor = 10.06

fs_command = "\?FS"
# K3NG Arduino Mega Command buffer array. Contains 3 commands: \?FS, \?GA, \?GE with updated data
mega_commands = ["\?FS","\?GA","\?GE"]
# AZ/EL global string variables contains what Set(P) commands wants. And is being modified with AZ/EL diffs
ga_mega_command = "\?GA180"
ge_mega_command = "\?GE30"

# Main commands and loop state set
#
#commands_state = ["quit", "slow_output", "full_output", "keep_silent", "GAmanuel", "GEmanuel"]
commands = ["EX", "SO", "FO", "KS", "GA", "GE"]
command_global = "keep_silent"

# Angiv filstien til Correctionstabellerne
az_coor_file = "az_coor_table.txt"
el_coor_file = "el_coor_table.txt"

# Opret en instans af AZ- / EL- Correction og indlæs data fra de to filer
az_coor_tbl = Correction_table(az_coor_file)
el_coor_tbl = Correction_table(el_coor_file)
    
    # Eksempel på at interpolere en værdi
#    target_x = 150
#    interpolated_value = az_coor_tbl.interpolate(target_x, az_coor_tbl.data_list)
    
#    if interpolated_value:
#        print(f"Interpoleret værdi for {target_x}: {interpolated_value}")
#    else:
#        print("Kunne ikke finde en passende interpolation.")

print(az_coor_tbl.data_list)  # Data fra az-file
print(el_coor_tbl.data_list)  # Data fra el-file

#    print(el_coor_tbl.data_list)  # Data fra el-file
#    print(az_coor_tbl.interpolate(157, az_coor_tbl.data_list))  # Interpoler for x = 150 i data_list1


def out_log_file(diff_file, az_f, el_f):
    nu = datetime.now()
    # Formatér dato og tid som en string
    dato_tid_streng = nu.strftime("%Y-%m-%d %H:%M:%S")
    # Skriv en string til filen
    out_text = dato_tid_streng + ";" + \
                "AZ_Set;" + "{:.2f}".format(az_set_global) + ";" \
                "AZ_diff;" + az_diff(az_f) + ";" \
                "EL_Set;" + "{:.2f}".format(el_set_global) + ";" \
                "EL_diff;" + el_diff(el_f) + "\n"
    # Output result to screen and text file
    diff_file.write(out_text)
#    print(out_text)

def el_diff(el_float): # Procedure returns string EL difference with 2 decimal points
    return f"{(el_raw_global - el_float):.2f}"

def az_diff(az_float): # Procedure returns string AZ difference with 2 decimal points
    return f"{(az_raw_global - az_float):.2f}"

def parse_az_el(data):
# Check if data[0] = "P". Else check på length of data. More than 14-15 char means defect input like "220.3 35.6\nP 220.3 "
# Discard data and wait for another data input. It apairs when Star Tracker send position to Rotator Controller
# first time.
# If length of data = 1 and data[0] = "p" then it is "Get" /OK

    index_1 = 0
    index_2 = 0
    length = 0
    max_P_command_len = 15

    az = "999"
    el = "999"
    # Konvert data string to az- and el-string
    az_el_txt = data.decode('utf-8')
    length = len(az_el_txt)
#    print(az_el_txt, length)
    if az_el_txt[0] == "P" or az_el_txt[0] == "p":
        # Data message seems ok, so proceed
        if length <= max_P_command_len: # Max. "P XXX.XX XX.XX" + \n = 15
            for index, char in enumerate(az_el_txt):
                if char == " ":
                    if index_1 == 0:
                        index_1 = index
                    else:
                        index_2 = index
#            print(index_1, index_2, length)
            az = az_el_txt[index_1 + 1:index_2]
            el = az_el_txt[index_2 + 1:length - 1]
#    print(az, el)
    return az, el

def move_to_az_command(az):
    ga_command = ""
    # Format K3NG Extended Move commands: \?GA (go to AZ xxx.x) and \?GE (go to EL xx.x)
    # and put in global command buffer to USB Mega
    ga_command = mega_commands[1] + az  # Husk at afkorte mega_commands
    return ga_command

def move_to_el_command(el):
    ge_command = ""
    # Format K3NG Extended Move commands: \?GA (go to AZ xxx.x) and \?GE (go to EL xx.x)
    # and put in global command buffer to USB Mega
    ge_command = mega_commands[2] + el
    return ge_command

def az_send_str(az_l):
    az_string = "{:.2f}".format(az_l)  # Beholder kun 2 decimaler med linefeed ???
    return az_string

def el_send_str(el_l):
    el_string = "{:.2f}".format(el_l)  # Beholder kun 2 decimaler med linefeed
    return el_string

def extract_data(data):
# \!OKFS215.163380,+047.042171,0,0,+55.0681,+010.6171,1,2024-10-21 10:19:48Z;                                                     
    extracted_az_substring = ""
    az = 0.0
    el = 0.0

    ok_substr ="OKFS"
    # Test om data indeholder OKFS
    found = data.find(ok_substr)
    if found >= 0:
        # Find startpositionen af AZ substrengen
        # Hvis substrengen er fundet, træk den ud
        extracted_az_substring = data[found+4: found+14]
        extracted_el_substring = data[found+16: found+26]
#        print(extracted_el_substring)
        if extracted_az_substring == "000.000000":
            az = 0.0
            el = 0.0
#        elif extracted_el_substring == "00-0.00000":
#            az = 0.0
#            el = 0.0
        else:
            az = float(extracted_az_substring)
            el = float(extracted_el_substring)
    else:
#        print(data)
        az = 0.0
        el = 0.0
    return az, el

def handle_client(client_socket, file):
    """
    Behandler klientens anmodning. 
    Lukker forbindelse efter håndtering.
    """
    global az_set_global
    global el_set_global
    global az_rotor_global
    global el_rotor_global
    global ga_mega_command
    global ge_mega_command
                        
    out_speed = 0
    max_out = 10

    try:
        while True:
            out_speed += 1
            # Modtag data fra klienten
            data = client_socket.recv(1024)
            if data:
                # Få den nuværende dato og tid
                nu = datetime.now()
                # Formatér dato og tid som en string
                dato_tid_streng = nu.strftime("%Y-%m-%d %H:%M:%S")
                # Skriv en string til filen
                out_text = dato_tid_streng + ";" + data.decode('utf-8')
                # Output result to screen and text file
                file.write(out_text)
                # Return answer
                if data[0] == ord("P"):
                    # Sender et svar tilbage
                    client_socket.send(b'RPRT 0\n')
                    # Parse for requested az and el
                    az, el = parse_az_el(data)
                    if az == "999" and el == "999":
                        pass
                    else:
                        az_set_global = float(az) # Correction of Set(P) ga_mega_command
                        ga_mega_command = mega_commands[1] + "{:.2f}".format(coor_az_sink_value(float(az)))  # Husk at afkorte mega_commands
                        el_set_global = float(el) # Correction of Set(P) ga_mega_command
                        ge_mega_command = mega_commands[2] + "{:.2f}".format(coor_el_sink_value(float(el)))  # Husk at afkorte mega_commands
                        if command_global == "keep_silent":
                            print("SDRangel Set: ", float(az), float(el), ga_mega_command, ge_mega_command)
                if data[0] == ord("p"):
                    az_rotor_global = coor_az_source_value(az_raw_global) # Correction to Get(p) values back to source SDRangel
                    el_rotor_global = coor_el_source_value(el_raw_global) # Correction to Get(p) values back to source SDRangel
                    # Sender et svar tilbage
                    client_socket.send(az_send(az_rotor_global))
#  F.eks                  conn.sendall(b'85.00\n')
                    client_socket.send(el_send(el_rotor_global))
#  F.eks                  conn.sendall(b'20.00\n')
                    if command_global == "keep_silent" and out_speed == max_out:
                        print("SDRangel Get(p): ", az_send(az_rotor_global), el_send(el_rotor_global), out_speed)
            else:
#            if not data:  # Hvis der modtages 0 bytes, er forbindelsen lukket
                print("[*] Client closed the connection")
                break

            if out_speed > max_out:
                out_speed = 0
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Lukker klientens socket
        client_socket.close()

def start_server(port, file):
    """
    Starter serveren, accepterer og håndterer én forbindelse ad gangen.
    """
    while True:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Tillad genbrug af samme adresse
            server.bind(('0.0.0.0', port))
            server.listen(1)
            print(f"[*] Server listening on port {port}")

            # Accepter ny forbindelse
            client_socket, addr = server.accept()
            print(f"[*] Accepted connection from {addr}")

            # Håndter klientforbindelse
            handle_client(client_socket, file)
        except KeyboardInterrupt:
            print("[*] Server shutting down")
            break
        except Exception as e:
            print(f"[!] Server error: {e}")
        finally:
            server.close()
            print("[*] Restarting server...")

# Funktion til at læse fra USB i en separat tråd
def read_from_usb(stop_event,ser,file):

    global az_raw_global
    global el_raw_global

    sum_data = ""
    zulu_substr = "Z;"
    
    while not stop_event.is_set():
        if ser.in_waiting > 0:  # Tjek om der er data i buffer
            data = ser.read(ser.in_waiting).decode('utf-8')
            found = data.find(zulu_substr)
            if found >= 0:  # End of string with "Z;" found
                sum_data += data
#                print(sum_data)
                az, el = extract_data(sum_data)
                if az != 0.0:
                    az_raw_global = az
                if el != 0.0:
                    el_raw_global = el
                # Få den nuværende dato og tid
                nu = datetime.now()
                # Formatér dato og tid som en string
                dato_tid_streng = nu.strftime("%Y-%m-%d %H:%M:%S")
                # Skriv en string til filen
                out_text = dato_tid_streng + ";" + sum_data
                # Output result to screen and text file
                file.write(out_text)
                sum_data = ""
            else:
                sum_data += data

def write_to_usb(stop_event,ser):
# Tråd til at skrive AZ/EL command til USB Arduino Nano
    global command_global

    while not stop_event.is_set():
        if command_global == "keep_silent":
            # Pull 5 second for az/el
            ser.write((fs_command + '\r\n').encode('utf-8'))  # Send \?FS til USB Mega
            time.sleep(3)  # Asynkron pause
            ser.write((ga_mega_command + '\r\n').encode('utf-8'))  # Send \?GA til USB Mega
            time.sleep(1)  # Asynkron pause
            ser.write((ge_mega_command + '\r\n').encode('utf-8'))  # Send \?GE til USB Mega
            time.sleep(1)  # Asynkron pause
#        else:
            
#        ser.write((el_command + '\r\n').encode('utf-8'))  # Send EL til USB Mega
#        time.sleep(1)  # Asynkron pause

def handle_command(command):
#    commands_state = ["quit", "slow_output", "full_output", "keep_silent", "GAmanuel", "GEmanuel"]
#    commands = ["EX", "SO", "FO", "KS", "GA", "GE"]
    global command_global
    
    if command in commands:
        if command == "EX":
            command_global = "quit"
            print("Exiting program.")
        elif command == "SO":
            command_global = "slow_output"
            print("Outputting slowly...")
        elif command == "FO":
            command_global = "full_output"
            print("Displaying full output...")
        elif command == "KS":
            command_global = "keep_silent"
            print("Displaying no output")
        elif command == "GA":
            command_global = "GAmanuel"
            print("Manuel AZ adjust, CW/CCW")
        elif command == "GE":
            command_global = "GEmanuel"
            print("Manuel EL adjust, UP/DOWN")
    else:
        print("Invalid command.")

def coor_az_sink_value(az):
    # Correction of Set/GA value with AZ-difference
    # Correction in here is addition (az + az_coor)

    az_tuple = az_coor_tbl.interpolate_sink(az, az_coor_tbl.data_list)    
    if az_tuple[1] != 0.0:
        return az_tuple[0] + az_tuple[1]

def coor_el_sink_value(el):
    # Correction of Set/GE value with EL-difference
    # Correction in here is addition (el_l + el_coor)

    el_tuple = el_coor_tbl.interpolate_sink(el, el_coor_tbl.data_list)    
    
    if el_tuple[1] != 0.0:
        return el_tuple[0] + el_tuple[1]  # Husk at afkorte mega_commands

def coor_az_source_value(az):
    # Correction (az - az_coor)

    az_tuple = az_coor_tbl.interpolate_source(az, az_coor_tbl.data_list)
    return az_tuple[0] - az_tuple[1]

def coor_el_source_value(el):
    # Correction (el - el_coor)

    el_tuple = el_coor_tbl.interpolate_source(el, el_coor_tbl.data_list)
    return el_tuple[0] - el_tuple[1]


def az_send(az_l):
    # Procedure is called with AZ-value of the rotor as a float
    # and is must correct AZ-value with AZ-difference and return is as a string
    # Correction in here is subtraction (az_l - az_coor)
    
    az_string = "{:.2f}".format(az_l) + "\n"  # Beholder kun 2 decimaler med linefeed
#    az_string = "{:.2f}".format(az_l - az_coor) + "\n"  # Beholder kun 2 decimaler med linefeed
    az_send = az_string.encode('utf-8')
    return az_send

def el_send(el_l):
    # Procedure is called with EL-value of the rotor as a float
    # and is must correct the EL-value with EL-difference and return is as a string
    # Correction in here is subtraction (el_l - el_coor)
    
    el_string = "{:.2f}".format(el_l) + "\n"  # Beholder kun 2 decimaler med linefeed
#    el_string = "{:.2f}".format(el_l - el_coor) + "\n"  # Beholder kun 2 decimaler med linefeed
    el_send = el_string.encode('utf-8')
    return el_send

def main():
    global command_global
    global az_coor
    global el_coor
    increment_value = 0.1  # Increment value for C/W/U/D adjustment

    # Open Output log text file with data
    file = open("rotctld_log.txt", "a")

# Rotctld listen socket
# Eksempel på brug
#    if __name__ == "__main__":
#        PORT = 4575
#        FILE = "example.txt"  # Eksempel på en fil, der kan bruges i handle_client
    socket_thread = threading.Thread(target=start_server, args=(port,file))
    socket_thread.daemon = True
    socket_thread.start()
#    start_server(port, file)
    

    # Åbn seriel port (tilpas portnavn og baudrate til din enhed)
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)

    # Opret et globalt Stop flag for trådene
    stop_event = threading.Event()
    
    # Start en tråd til at læse fra USB
    read_thread = threading.Thread(target=read_from_usb, args=(stop_event,ser,file))
    read_thread.daemon = True
    read_thread.start()

    # Start en tråd til at skrive kommandoer til USB Arduino Nana
    write_thread = threading.Thread(target=write_to_usb, args=(stop_event,ser,))
    write_thread.daemon = True
    write_thread.start()

    # Start asynkron skrivning til USB
    #    await write_to_usb(ser)
#    commands_state = ["quit", "slow_output", "full_output", "keep_silent"]
#    commands = ["EX", "SO", "FO", "KS"]

    while command_global != "quit":
        # Test det med et input
        if command_global != "GAmanuel" and command_global != "GEmanuel":
            user_input = input("Enter a command: ").strip()
            handle_command(user_input)
        else:
            az_local = az_raw_global
            el_local = el_raw_global
            while command_global != "keep_silent":
                user_input = input("Enter Up/Down/Cw/ccW/Exit/Increment/Outfile/aZ/eL/Print: ").strip()
                match user_input:
                    case "u":
                        el_local += increment_value
                        print("You moved Up!", move_to_el_command(el_send_str(el_local)),
                            ", SDRangel Set EL:", move_to_el_command(el_send_str(el_set_global)),
                              ", Diff: ", el_diff(el_local))
                        ser.write((move_to_el_command(el_send_str(el_local)) + '\r\n').encode('utf-8'))  # Send \?GE til USB Mega
                    case "d":
                        el_local -= increment_value
                        print("You moved Down!", move_to_el_command(el_send_str(el_local)),
                              ", SDRangel Set EL:", move_to_el_command(el_send_str(el_set_global)),
                              ", Diff: ", el_diff(el_local))
                        ser.write((move_to_el_command(el_send_str(el_local)) + '\r\n').encode('utf-8'))  # Send \?GE til USB Mega
                    case "c":
                        az_local += increment_value
                        print("You moved Cw!", move_to_az_command(az_send_str(az_local)),
                              ", SDRangel Set AZ:", move_to_el_command(el_send_str(az_set_global)),
                              ", Diff: ", az_diff(az_local))
                        ser.write((move_to_az_command(az_send_str(az_local)) + '\r\n').encode('utf-8'))  # Send \?GA til USB Mega
                    case "w":
                        az_local -= increment_value
                        print("You moved ccW!", move_to_az_command(az_send_str(az_local)),
                              ", SDRangel Set AZ:", move_to_el_command(el_send_str(az_set_global)),
                              ", Diff: ", az_diff(az_local))
                        ser.write((move_to_az_command(az_send_str(az_local)) + '\r\n').encode('utf-8'))  # Send \?GA til USB Mega
                    case "e":
                        print("You pressed Exit!")
                        command_global = "keep_silent"
                    case "o":
                        print("You logged to Outfile:")
                        # Få den nuværende dato og tid
                        out_log_file(file, az_local, el_local)
                    case "i":
                        try:
                            user_input = input("Input Increment value: ")
                            increment_value = float(user_input)
#                            print("Du indtastede float-værdien:", increment_value)
                        except ValueError:
                            print("Det indtastede er ikke et gyldigt decimaltal.")
                    case "p":
                        print("AZ-coor: ", str(az_coor), "EL-coor: ", str(el_coor))
                    case "z":
                        try:
                            user_input = input("Input aZimuth diff value: ")
                            az_coor = float(user_input)
#                            print("Du indtastede float-værdien:", increment_value)
                        except ValueError:
                            print("Det indtastede er ikke et gyldigt decimaltal.")
                    case "l":
                        try:
                            user_input = input("Input eLevation diff value: ")
                            el_coor = float(user_input)
#                            print("Du indtastede float-værdien:", increment_value)
                        except ValueError:
                            print("Det indtastede er ikke et gyldigt decimaltal.")
                    case _:
                        print("Invalid direction")

# Wait for user stop command EX
#    command = input("Indtast AZ eller EL for en måling eller EX for End: ") # Venter på tom CR
#    if command == "EX":
    stop_event.set()

    # Wait Thread stoped
    print("Trådene lukker ned")
    file.close()
    read_thread.join()
    write_thread.join()

# start main program
if __name__ == '__main__':
    main()
