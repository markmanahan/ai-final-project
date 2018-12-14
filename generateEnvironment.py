from __future__ import print_function
from __future__ import division

from builtins import range
from past.utils import old_div
import MalmoPython
import json
import logging
import math
import os
#import random
import sys
import time
#import re
import uuid
from collections import namedtuple
#from operator import add
#from random import *
#import numpy as np
import QLearning3
import copy


EntityInfo = namedtuple('EntityInfo', 'x, y, z, name')

# Create one agent host for parsing:
agent_hosts = [MalmoPython.AgentHost()]

# Parse the command-line options:
agent_hosts[0].addOptionalFlag( "debug,d", "Display debug information.")
agent_hosts[0].addOptionalIntArgument("agents,n", "Number of agents to use, including observer.", 2)
agent_hosts[0].addOptionalStringArgument("map,m", "Name of map to be used", "openClassic")

try:
    agent_hosts[0].parse( sys.argv )
except RuntimeError as e:
    print('ERROR:',e)
    print(agent_hosts[0].getUsage())
    exit(1)
if agent_hosts[0].receivedArgument("help"):
    print(agent_hosts[0].getUsage())
    exit(0)

DEBUG = agent_hosts[0].receivedArgument("debug")
INTEGRATION_TEST_MODE = agent_hosts[0].receivedArgument("test")
agents_requested = agent_hosts[0].getIntArgument("agents")
NUM_AGENTS = max(1, agents_requested) # Will be NUM_AGENTS robots running around, plus one static observer.
map_requested = agent_hosts[0].getStringArgument("map")
# Create the rest of the agent hosts - one for each robot, plus one to give a bird's-eye view:
agent_hosts += [MalmoPython.AgentHost() for x in range(1, NUM_AGENTS) ]

# Set up debug output:
for ah in agent_hosts:
    ah.setDebugOutput(DEBUG)    # Turn client-pool connection messages on/off.

if sys.version_info[0] == 2:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)  # flush print output immediately
else:
    import functools
    print = functools.partial(print, flush=True)


def safeStartMission(agent_host, my_mission, my_client_pool, my_mission_record, role, expId):
    used_attempts = 0
    max_attempts = 5
    print("Calling startMission for role", role)
    while True:
        try:
            # Attempt start:
            agent_host.startMission(my_mission, my_client_pool, my_mission_record, role, expId)
            break
        except MalmoPython.MissionException as e:
            errorCode = e.details.errorCode
            if errorCode == MalmoPython.MissionErrorCode.MISSION_SERVER_WARMING_UP:
                print("Server not quite ready yet - waiting...")
                time.sleep(2)
            elif errorCode == MalmoPython.MissionErrorCode.MISSION_INSUFFICIENT_CLIENTS_AVAILABLE:
                print("Not enough available Minecraft instances running.")
                used_attempts += 1
                if used_attempts < max_attempts:
                    print("Will wait in case they are starting up.", max_attempts - used_attempts, "attempts left.")
                    time.sleep(2)
            elif errorCode == MalmoPython.MissionErrorCode.MISSION_SERVER_NOT_FOUND:
                print("Server not found - has the mission with role 0 been started yet?")
                used_attempts += 1
                if used_attempts < max_attempts:
                    print("Will wait and retry.", max_attempts - used_attempts, "attempts left.")
                    time.sleep(2)
            else:
                print("Other error:", MalmoPython.MissionExceptionDetails.message)
                print("Waiting will not help here - bailing immediately.")
                exit(1)
        if used_attempts == max_attempts:
            print("All chances used up - bailing now.")
            exit(1)
    print("startMission called okay.")

def safeWaitForStart(agent_hosts):
    print("Waiting for the mission to start", end=' ')
    start_flags = [False for a in agent_hosts]
    start_time = time.time()
    time_out = 120  # Allow a two minute timeout.
    while not all(start_flags) and time.time() - start_time < time_out:
        states = [a.peekWorldState() for a in agent_hosts]
        start_flags = [w.has_mission_begun for w in states]
        errors = [e for w in states for e in w.errors]
        if len(errors) > 0:
            print("Errors waiting for mission start:")
            for e in errors:
                print(e.text)
            print("Bailing now.")
            exit(1)
        time.sleep(0.1)
        print(".", end=' ')
    if time.time() - start_time >= time_out:
        print("Timed out while waiting for mission to start - bailing.")
        exit(1)
    print()
    print("Mission has started.")


def getLayout(name):
    matrix = tryToLoad("layouts/" + name)
    return matrix

def tryToLoad(fullname):
    if (not os.path.exists(fullname)): return None
    f = open(fullname)
    Matrix = [line.strip() for line in f]
    f.close()
    return Matrix

level_mat = getLayout(map_requested + ".lay")

def drawItems(x, z):
    return  '<DrawItem x="' + str(x) + '" y="56" z="' + str(z) + '" type="apple"/>'


def GenBlock(x, y, z, blocktype):
    return '<DrawBlock x="' + str(x) + '" y="' + str(y) + '" z="' + str(z) + '" type="' + blocktype + '"/>'

def GenPlayerStart(x, z):
    return '<Placement x="' + str(x + 0.5) + '" y="56" z="' + str(z + 0.5) + '" yaw="180"/>'

def GenEnemyStart(x, z):
    return '<Placement x="' + str(x + 0.5) + '" y="56" z="' + str(z + 0.5) + '" yaw="0"/>'

pStart = {'x': 0, 'z': 2}
eStart = {'x': 0, 'z': -1}

TIMERATE = 50


def mazeCreator():
    genstring = ""
    genstring += GenBlock(0, 65, 0, "glass") + "\n"
    for i in range(len(level_mat)):
        for j in range(len(level_mat[0])):

            if level_mat[i][j] == "%":
                genstring += GenBlock(i, 54, j, "diamond_block") + "\n"
                genstring += GenBlock(i, 55, j, "diamond_block") + "\n"
                genstring += GenBlock(i, 56, j, "diamond_block") + "\n"

            elif level_mat[i][j] == "P":
                pStart['x'] = i
                pStart['z'] = j
                #pCurr['x'] = i
                #pCurr['z'] = j

            elif level_mat[i][j] == ".":
                genstring += GenBlock(i, 55, j, "glowstone") + "\n"

            elif level_mat[i][j] == "G":
                eStart['x'] = i
                eStart['z'] = j
                #eCurr['x'] = i
                #eCurr['z'] = j

    return genstring

def invMake():
    xml = ""
    for i in range(0, 39):
        xml += '<InventoryObject type="iron_sword" slot="0" quantity="1"/><InventoryObject type="potion">'
    return(xml)

def getXML(reset):
    ARENA_WIDTH = 10
    ARENA_BREADTH = 10
    # Set up the Mission XML:
    xml = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
            <Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
              <About>
                <Summary>Hello world!</Summary>
              </About>

              <ModSettings>
                <MsPerTick>''' + str(TIMERATE) + '''</MsPerTick>
              </ModSettings>
              <ServerSection>
                <ServerInitialConditions>
                 <Time>
                    <StartTime>12000</StartTime>
                     <AllowPassageOfTime>false</AllowPassageOfTime>
                 </Time>
                </ServerInitialConditions>
                <ServerHandlers>
                  <FlatWorldGenerator generatorString="3;7,44*49,73,35:1,159:4,95:13,35:13,159:11,95:10,159:14,159:6,35:6,95:6;12;"/>
                  <DrawingDecorator>
                    <DrawLine x1="-4" y1="57" z1="4" x2="4" y2="57" z2="4" type="gold_block"/>
                    <DrawLine x1="4" y1="57" z1="4" x2="4" y2="57" z2="-4" type="gold_block"/>
                    <DrawLine x1="-4" y1="57" z1="-4" x2="4" y2="57" z2="-4" type="gold_block"/>
                    <DrawLine x1="-4" y1="57" z1="4" x2="-4" y2="57" z2="-4" type="gold_block"/>
                  </DrawingDecorator>
                  <ServerQuitFromTimeUp timeLimitMs="500000"/>
                </ServerHandlers>
              </ServerSection>
              <AgentSection mode="Survival">
                <Name>Player</Name>
                <AgentStart> '''   + GenPlayerStart(pStart['x'], pStart['z']) +  '''

                <Inventory><InventoryItem type="iron_sword" slot="0" quantity="1"/></Inventory>
                </AgentStart>
                <AgentHandlers>


                <ChatCommands/>
                <ContinuousMovementCommands turnSpeedDegs="420"/>
                <InventoryCommands/>
                <ObservationFromRay/>
                <ObservationFromHotBar/>
                  <MissionQuitCommands/>
                  <ObservationFromFullStats/>
                  <ObservationFromNearbyEntities>
                    <Range name="entities" xrange="'''+str(ARENA_WIDTH)+'''" yrange="2" zrange="'''+str(ARENA_BREADTH)+'''" />
                  </ObservationFromNearbyEntities>

                </AgentHandlers>
              </AgentSection>
              <AgentSection mode="Survival">
                <Name>Enemy</Name>
                <AgentStart> 
                '''   + GenEnemyStart(eStart['x'], eStart['z']) +  ''' 
                <Inventory><InventoryItem type="iron_sword" slot="0" quantity="1"/></Inventory>
                </AgentStart>
                <AgentHandlers>
                <ChatCommands/>

                  <ContinuousMovementCommands turnSpeedDegs="420"/>
                  <ObservationFromRay/>
                  <InventoryCommands/>
                  <ObservationFromHotBar/>
                  <MissionQuitCommands/>
                  <ObservationFromFullStats/>
                  <ObservationFromNearbyEntities>
                    <Range name="entities" xrange="'''+str(ARENA_WIDTH)+'''" yrange="2" zrange="'''+str(ARENA_BREADTH)+'''" />
                  </ObservationFromNearbyEntities>
                </AgentHandlers>
              </AgentSection>
            </Mission>'''

    return xml

client_pool = MalmoPython.ClientPool()
for x in range(10000, 10000 + NUM_AGENTS + 1):
    client_pool.add( MalmoPython.ClientInfo('127.0.0.1', x) )


print("Running mission")
# Create mission xml - use forcereset if this is the first mission.

experimentID = str(uuid.uuid4())


time.sleep(1)
running = True

current_pos = [(0,0) for x in range(NUM_AGENTS)]
# When an agent is killed, it stops getting observations etc. Track this, so we know when to bail.
my_mission = MalmoPython.MissionSpec(getXML("true"), True)
agents = QLearning3.TabQAgent()



timed_out = False

# Main mission loop

num_repeats = 20
cumulative_reward = 0
rewards = []


###  Uncomment this section if you want to load from previous training ###

try:
    with open('qtableE.txt', 'r') as saveFile:
        print("loading qtable...\n\n")
        agents.q_table = json.loads(saveFile.read())
        #agents.enemyQ_table = copy.deepcopy(agents.q_table)
except:
    print("File not found\n")
    exit(1)

for i in range(num_repeats):

    my_mission_record = MalmoPython.MissionRecordSpec()

    for j in range(len(agent_hosts)):
        safeStartMission(agent_hosts[j], my_mission, client_pool, my_mission_record, j, experimentID)

    safeWaitForStart(agent_hosts)

    print('Repeat %d of %d' % (i + 1, num_repeats))
    agent_hosts[0].sendCommand("chat /replaceitem entity @a slot.hotbar.1 minecraft:potion 1 0 {Potion:minecraft:strong_healing}")
    agent_hosts[0].sendCommand("chat /replaceitem entity @a slot.weapon.offhand minecraft:shield")
    agent_hosts[0].sendCommand("chat /gamerule naturalRegeneration false")

    #ah = agent_hosts[i]
    rewards.append(agents.run(agent_hosts[0], agent_hosts[1], TIMERATE))
    cumulative_reward += rewards[-1]

    ws = agent_hosts[-1].getWorldState()
    while ws.is_mission_running:
        agent_hosts[-1].sendCommand("quit")
        time.sleep(1)
        print('waiting..\n')
        ws = agent_hosts[-1].getWorldState()

     #   pass




print("Waiting for mission to end ", end=' ')
# Mission should have ended already, but we want to wait until all the various agent hosts
# have had a chance to respond to their mission ended message.
hasEnded = True
while not hasEnded:
    hasEnded = True # assume all good
    print(".", end="")
    time.sleep(0.1)
    for ah in agent_hosts:
        world_state = ah.getWorldState()
        if world_state.is_mission_running:
            hasEnded = False # all not good

print("Cumulative Reward: ", cumulative_reward)
print("All rewards:\n", rewards)

#with open('qtableE.txt', 'w') as saveFile:
#    saveFile.write(json.dumps(agents.q_table))

