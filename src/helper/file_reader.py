

def read_config_file(file = 'info_files/config.txt'):
    config = {}
    with open(file) as f:
        while True:
            read = f.readline()
            if(read == ''):
                break
            if(read.__contains__('#')): # allows files to have comments
                continue
            read = read.removesuffix('\n').split('=')
            config[read[0]] = read[1]
        return config
    

def read_waypoints(file = 'info_files/waypoints.txt'):
    waypoints = []
    feet = False
    with open(file) as f:
        while True:
            read = f.readline()
            if(read == ''):
                break
            if(read == 'feet'):
                feet = True
            if(read.__contains__('#')):
                continue
            read = read.removesuffix('\n').split(',')
            waypoints.append([float(read[0]), float(read[1]), (float(read[2])/3.281) if feet else float(read[2])])

    return waypoints

def read_geofence(file = 'info_files/fence.txt'):
    geofence = []
    with open(file) as f:
        while True:
            read = f.readline()
            if(read == ''):
                break
            if(read.__contains__('#')):
                continue
            read = read.removesuffix('\n').split(',')
            geofence.append([float(read[0]),float(read[1])])

    return geofence

def file_to_list(file):
    items = []
    with open(file) as f:
        while True:
            read = f.readline()
            if read == '':
                return items
            if read.__contains__("#"):
                continue
            read = read.removesuffix('\n')
            items.append(read)

def read_file(file):
    items = []
    with open(file) as f:
        while True:
            read = f.readline()
            if(read == ''):
                return items
            if(read.__contains__('#')):
                continue
            read = read.removesuffix('\n')
            
            #FILE REDIRECT
            if read.__len__() >= 7 and read[0:7] == "redir->":
                print(f'redirection encountered. file name: {read[7:]}')

            # REPOSITION
            if read.__len__() >= 6 and read[0:6] == "repo->":
                target_repo = []
                read = read[6:]
                while True:
                    if not read.__contains__(","):
                        target_repo.append(float(read))
                        break
                    target_repo.append(float(read[0:read.index(',')]))
                    read = read[read.index(",")+1:]
                print(f'reposition drone to {target_repo}')
            
    return items
            
'''Need to create some sort of scripting/redirection system. if a mission file had to read another file for info, i need to 
    write a standard that can do that. Thinking, if( read == 'redir->[file]): then read [file] recursively etc
    read = "redir->[file name]"
    print(read[0:7]) prints redir->
    print(read[7:]) prints [file name]
    
    redir-> will redirect attention to given file. it will read the commands of the file passed and execute it before returning to current file
    repo-> will reposition the drone given lat,long,alt coordinates. format: repo->[lat],[long],[rel_alt(meters)]
    altchange->[desired relative altitude] - will instruct drone to change its altitude
    land->home or land->here - 'home' will tell drone to land at where it left from. 'here' says to land right where it is
    speed->[new speed] - instructs drone to change speed to [new speed]
    mode->[mode name] - instructs drone to change mode
    req->[message name] - requests a message
    sendcmd->[command id]
    '''