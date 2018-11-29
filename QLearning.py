from __future__ import print_function

from future import standard_library

standard_library.install_aliases()
from builtins import range
from builtins import object
import MalmoPython
import json
import logging
import os
import random
import sys
import time
import itertools
import math
#from numpy import argmax

if sys.version_info[0] == 2:
    import Tkinter as tk
else:
    import tkinter as tk


class TabQAgent(object):
    """Tabular Q-learning agent for discrete state/action spaces."""

    def __init__(self):

        self.epsilon = 0.05  # exploration rate
        self.alpha = 0.2     # learning rate
        self.gamma = 0.8  # reward discount factor

        self.logger = logging.getLogger(__name__)
        if False:  # True if you want to see more information
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        self.logger.addHandler(logging.StreamHandler(sys.stdout))


        self.movementActions = ["move 0", "move 1", "move -1", "strafe 1", "strafe -1"]
        self.turnSpeed = ["turn 0", "turn 0.33", "turn 0.66", "turn 1", "turn -0.33", "turn -0.66", "turn -1"]
        self.hotkeyChoice = ["hotbar.1 1", "hotbar.2 1"] #Ben: Might be bugged
        self.mouseAction = ["attack 1", "use 1"]
        #self.directions = ["setYaw 0", "setYaw 30", "setYaw 60", "setYaw 90", "setYaw 120"]

        self.playerX = 0
        self.playerZ = 0
        self.playerYaw = 0
        self.playerLife = 10


        self.actions = list(itertools.product(self.movementActions, self.turnSpeed, self.hotkeyChoice, self.mouseAction)) #total number of actions: 140
        print("size of actions: ", len(self.actions))
        self.q_table = {}
        self.canvas = None
        self.root = None
        
    ### Change q_table to reflect what we have learnt.
    # Inputs: reward - int, current_state - coordinate tuple, prev_state - coordinate tuple, prev_a - int
    # Output: updated q_table
    def updateQTable(self, reward, current_state, prev_state, prev_a):
        # Keeping a running average of all previously observed samples
        self.q_table[prev_state][prev_a] = (1 - self.alpha) * self.q_table[prev_state][prev_a] + self.alpha * (reward + (self.gamma * max(self.q_table[current_state][i] for i in range(len(self.actions)))))

        return
    ### Change q_table to reflect what we have learnt upon reaching the terminal state.
    # Input: reward - int, prev_state - coordinate tuple, prev_a - int
    # Output: updated q_table
    def updateQTableFromTerminatingState(self, reward, prev_state, prev_a):
        self.q_table[prev_state][prev_a] = reward
        return

    def act(self, world_state, agent_host, current_r, enemy_state):
        obs_text = world_state.observations[-1].text
        enemyOb = enemy_state.observations[-1].text
        obs = json.loads(obs_text)  # most recent observation
        self.logger.debug(obs)
        if not u'XPos' in obs or not u'ZPos' in obs:
            self.logger.error("Incomplete observation received: %s" % obs_text)
            return 0


        self.playerYaw = obs[u'Yaw']
        self.playerX = obs[u'XPos']
        self.playerZ = obs[u'ZPos']
        self.playerLife = obs[u'Life']


        #current_s needs to be changed to include,
        canAttack = 0   # can only be 0 or 1
        distanceFromEnemy = 100
        angleFromEnemy = 0

        if u'LineOfSight' in obs:
            print(obs[u'LineOfSight'])
            if(obs[u'LineOfSight'][u'inRange']):
                print("in range\n")
                canAttack = 1
        else:
            print("No line of sight")

        if u'entities' in obs:
            for e in obs[u'entities']:
                if e[u'Name'] == 'Enemy':

                    print("entity: ",)
                    distanceFromEnemy = int(math.sqrt((e["x"] - self.playerX)*(e["x"] - self.playerX) + (e["z"] - self.playerZ)*(e["z"] - self.playerZ)))
                    yaw = -180 * math.atan2(e["x"] - self.playerX, e["z"] - self.playerZ) / math.pi
                    print("My yaw: ", self.playerYaw, ", calc. yaw: ", yaw, ", Difference: ", yaw - self.playerYaw)
                    difference = yaw - self.playerYaw
                    while difference < -180:
                        difference += 360;
                    while difference > 180:
                        difference -= 360;
                    difference /= 180.0
                    print("Final distance: ", difference)
                    angleFromEnemy = difference

        else:
            print("p a n i c\n\n\n")
            print(obs)


                                    # was: (int(obs[u'XPos']), int(obs[u'ZPos']))
        current_s = "%d:%d:%.2f" % (canAttack, distanceFromEnemy, float(angleFromEnemy))
        self.logger.debug("State: %s (x = %.2f, z = %.1f)" % (current_s, float(obs[u'XPos']), float(obs[u'ZPos'])))
        if current_s not in self.q_table:
            self.q_table[current_s] = ([0] * len(self.actions))

        # update Q values
        if self.prev_s is not None and self.prev_a is not None:
            self.updateQTable(current_r, current_s, self.prev_s, self.prev_a)

        #self.drawQ(curr_x=int(obs[u'XPos']), curr_y=int(obs[u'ZPos']))

        # select the next action (find a s.t. self.actions[a] == next action)
        if random.random() <= self.epsilon:
            next_action = random.choice(len(self.actions))
        else:
            #print(self.q_table[current_s])
            maxExp = max(self.q_table[current_s])
            print("max is ",maxExp)
            bestResults = []
            for i in range(len(self.actions)):
                if self.q_table[current_s][i] == maxExp:
                    bestResults.append(i)
            next_action = random.choice(bestResults)

            print(next_action)
            print(self.actions[next_action])



        # try to send the selected action to agent, only update prev_s if this succeeds
        for command in self.actions[next_action]:
            agent_host.sendCommand(command)
        self.prev_s = current_s
        self.prev_a = next_action



        return current_r


    #TEMP Code for enemy from Reflex

    def enemyAgentMoveRand(self, agent, ws):
        legalLST = ["right", "left", "forward", "back"]
        y = random.randint(0,len(legalLST)-1)
        togo = legalLST[y]
        if togo == "right":
            self.moveRight(agent)

        elif togo == "left":
            self.moveLeft(agent)

        elif togo == "forward":
            self.moveStraight(agent)

        elif togo == "back":
            self.moveBack(agent)


    def moveRight(self, ah):
        ah.sendCommand("strafe 1")


    def moveLeft(self, ah):
        ah.sendCommand("strafe -1")


    def moveStraight(self, ah):
        ah.sendCommand("move 1")


    def moveBack(self, ah):
        ah.sendCommand("move -1")








    # do not change this function
    def run(self, agent_host0, agent_host1):
        """run the agent on the world"""

        total_reward = 0

        self.prev_s = None
        self.prev_a = None

        state1 = agent_host0.getWorldState()

        if state1.is_mission_running and state1.number_of_observations_since_last_state > 0:
            print("here!\n")
            msg = state1.observations[-1].text
            ob = json.loads(msg)
        elif state1.is_mission_running:
            state1 = agent_host1.getWorldState()
            while state1.number_of_observations_since_last_state == 0:
                print("waiting..")
                time.sleep(1)

        if(ob['Name'] == 'Player'):
            player = agent_host0
            #playerOb = ob
            enemy = agent_host1
            #enemyOb = json.loads((enemy.getWorldState()).observations[-1].text)
        else:
            player = agent_host1
            enemy = agent_host0
            #enemyOb = ob
            #playerOb = json.loads(player.getWorldState().observations[-1].text)

        #unrolled first_action
        current_r = 0
        while True:
            time.sleep(0.1)
            player_state = player.getWorldState()
            enemy_state = enemy.getWorldState()
            for error in player_state.errors:
                self.logger.error("Error: %s" % error.text)
            for reward in player_state.rewards:
                current_r += reward.getValue()
                print("current_r ", current_r)
            if player_state.is_mission_running and len(player_state.observations) > 0 and not \
            player_state.observations[-1].text == "{}":
                total_reward += self.act(player_state, player, current_r, enemy_state)
                self.enemyAgentMoveRand(enemy, enemy.getWorldState())
                break
            if not player_state.is_mission_running:
                break




        player_state = player.getWorldState()
        while player_state.is_mission_running:
            current_r = 0

            # wait for non-zero reward
            while player_state.is_mission_running and current_r == 0:
                time.sleep(0.1)
                player_state = player.getWorldState()
                for error in player_state.errors:
                    self.logger.error("Error: %s" % error.text)
                for reward in player_state.rewards:
                    current_r += reward.getValue()
                    print("current_r", current_r)
            # allow time to stabilise after action
            while True:
                time.sleep(0.1)
                player_state = player.getWorldState()
                for error in player_state.errors:
                    self.logger.error("Error: %s" % error.text)
                for reward in player_state.rewards:
                    current_r += reward.getValue()
                if player_state.is_mission_running and len(player_state.observations) > 0 and not \
                player_state.observations[-1].text == "{}":
                    total_reward += self.act(player_state, player, current_r)
                    self.enemyAgentMoveRand(enemy, enemy.getWorldState())
                    break
                if not player_state.is_mission_running:
                    break




        # process final reward
        total_reward += current_r

        # update Q values
        if self.prev_s is not None and self.prev_a is not None:
            self.updateQTableFromTerminatingState(current_r, self.prev_s, self.prev_a)


        return 0

    # do not change this function
    def drawQ(self, curr_x=None, curr_y=None):
        scale = 50
        world_x = 6
        world_y = 14
        if self.canvas is None or self.root is None:
            self.root = tk.Tk()
            self.root.wm_title("Q-table")
            self.canvas = tk.Canvas(self.root, width=world_x * scale, height=world_y * scale, borderwidth=0,
                                    highlightthickness=0, bg="black")
            self.canvas.grid()
            self.root.update()
        self.canvas.delete("all")
        action_inset = 0.1
        action_radius = 0.1
        curr_radius = 0.2
        action_positions = [(0.5, action_inset), (0.5, 1 - action_inset), (action_inset, 0.5), (1 - action_inset, 0.5)]
        # (NSWE to match action order)
        min_value = -20
        max_value = 20
        for x in range(world_x):
            for y in range(world_y):
                s = "%d:%d" % (x, y)
                self.canvas.create_rectangle(x * scale, y * scale, (x + 1) * scale, (y + 1) * scale, outline="#fff",
                                             fill="#002")
                for action in range(4):
                    if not s in self.q_table:
                        continue
                    value = self.q_table[s][action]
                    color = int(255 * (value - min_value) / (max_value - min_value))  # map value to 0-255
                    color = max(min(color, 255), 0)  # ensure within [0,255]
                    color_string = '#%02x%02x%02x' % (255 - color, color, 0)
                    self.canvas.create_oval((x + action_positions[action][0] - action_radius) * scale,
                                            (y + action_positions[action][1] - action_radius) * scale,
                                            (x + action_positions[action][0] + action_radius) * scale,
                                            (y + action_positions[action][1] + action_radius) * scale,
                                            outline=color_string, fill=color_string)
        if curr_x is not None and curr_y is not None:
            self.canvas.create_oval((curr_x + 0.5 - curr_radius) * scale,
                                    (curr_y + 0.5 - curr_radius) * scale,
                                    (curr_x + 0.5 + curr_radius) * scale,
                                    (curr_y + 0.5 + curr_radius) * scale,
                                    outline="#fff", fill="#fff")
        self.root.update()



'''



if sys.version_info[0] == 2:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)  # flush print output immediately
else:
    import functools

    print = functools.partial(print, flush=True)

agent = TabQAgent()
agent_host = MalmoPython.AgentHost()
try:
    agent_host.parse(sys.argv)
except RuntimeError as e:
    print('ERROR:', e)
    print(agent_host.getUsage())
    exit(1)

# -- set up the mission -- #
mission_file = './qlearning.xml'
with open(mission_file, 'r') as f:
    print("Loading mission from %s" % mission_file)
    mission_xml = f.read()
    my_mission = MalmoPython.MissionSpec(mission_xml, True)

# add some random holes in the ground to spice things up
for x in range(1, 3):
    for z in range(1, 13):
        if random.random() < 0.1:
            my_mission.drawBlock(x, 45, z, "water")

max_retries = 3

num_repeats = 150

cumulative_rewards = []
for i in range(num_repeats):

    print()
    print('Repeat %d of %d' % (i + 1, num_repeats))

    my_mission_record = MalmoPython.MissionRecordSpec()

    for retry in range(max_retries):
        try:
            agent_host.startMission(my_mission, my_mission_record)
            break
        except RuntimeError as e:
            if retry == max_retries - 1:
                print("Error starting mission:", e)
                exit(1)
            else:
                time.sleep(2.5)

    print("Waiting for the mission to start", end=' ')
    world_state = agent_host.getWorldState()
    while not world_state.has_mission_begun:
        print(".", end="")
        time.sleep(0.1)
        world_state = agent_host.getWorldState()
        for error in world_state.errors:
            print("Error:", error.text)
    print()

    # -- run the agent in the world -- #
    cumulative_reward = agent.run(agent_host)
    print('Cumulative reward: %d' % cumulative_reward)
    cumulative_rewards += [cumulative_reward]

    # -- clean up -- #
    time.sleep(0.5)  # (let the Mod reset)

print("Done.")

print()
print("Cumulative rewards for all %d runs:" % num_repeats)
print(cumulative_rewards)

'''